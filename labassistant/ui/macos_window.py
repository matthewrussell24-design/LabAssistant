"""Native AppKit window hosting the local LabAssistant research workspace."""

from __future__ import annotations

import json
import os
import select
import signal
import threading
from collections.abc import Callable, Sequence

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSMakeRect,
    NSMakeSize,
    NSModalResponseOK,
    NSObject,
    NSOpenPanel,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSURL
from CoreFoundation import CFRunLoopGetMain, CFRunLoopWakeUp
from WebKit import WKWebView, WKWebViewConfiguration

from labassistant.application import DLSAnalysisResult, list_experiments, restore_dls_experiment
from labassistant.ui.presenters import persisted_history_payload, result_payload
from labassistant.ui.web_workspace import WORKSPACE_HTML


class WorkspaceController(NSObject):
    analyze_dataset: Callable[[Sequence[str]], DLSAnalysisResult]
    webview: WKWebView

    def initWithAnalyzer_(self, analyzer):
        self = objc.super(WorkspaceController, self).init()
        if self is None:
            return None
        self.analyze_dataset = analyzer
        self.webview = None
        self.pending_paths = ()
        return self

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        body = message.body()
        action = body.get("action") if hasattr(body, "get") else body.objectForKey_("action")
        if action == "import_dls":
            self.selectDLSDataset()
        elif action == "open_experiment":
            record_id = body.get("record_id") if hasattr(body, "get") else body.objectForKey_("record_id")
            self.restoreExperiment_(record_id)

    def webView_didFinishNavigation_(self, webview, navigation):
        self.loadPersistedHistory()
        if self.pending_paths:
            paths = self.pending_paths
            self.pending_paths = ()
            self.analyzePaths_(paths)

    def loadPersistedHistory(self):
        try:
            listings = list_experiments()
        except Exception:
            listings = ()
        payload = persisted_history_payload(listings)
        script = f"window.labassistantSetPersistedHistory({json.dumps(payload)})"
        self.webview.evaluateJavaScript_completionHandler_(script, None)

    def restoreExperiment_(self, record_id):
        try:
            payload = result_payload(restore_dls_experiment(str(record_id)))
        except Exception as error:
            script = f"window.labassistantShowError({json.dumps(str(error))})"
        else:
            script = f"window.labassistantAddResult({json.dumps(payload)})"
        self.webview.evaluateJavaScript_completionHandler_(script, None)

    def selectDLSDataset(self):
        panel = NSOpenPanel.openPanel()
        panel.setTitle_("Select DLS dataset files")
        panel.setAllowsMultipleSelection_(True)
        panel.setCanChooseDirectories_(False)
        panel.setCanChooseFiles_(True)
        panel.setAllowedFileTypes_(["csv", "txt", "tsv", "xlsx", "xls"])
        if panel.runModal() == NSModalResponseOK:
            self.analyzePaths_([url.path() for url in panel.URLs()])

    def analyzePaths_(self, paths):
        try:
            payload = result_payload(self.analyze_dataset(list(paths)))
        except Exception as error:
            script = f"window.labassistantShowError({json.dumps(str(error))})"
        else:
            script = f"window.labassistantAddResult({json.dumps(payload)})"
        self.webview.evaluateJavaScript_completionHandler_(script, None)


class ApplicationDelegate(NSObject):
    def initWithTerminationCallback_(self, callback):
        self = objc.super(ApplicationDelegate, self).init()
        if self is None:
            return None
        self.termination_callback = callback
        return self

    def applicationShouldTerminateAfterLastWindowClosed_(self, application):
        return True

    def applicationWillTerminate_(self, notification):
        if self.termination_callback is not None:
            self.termination_callback()


def run_native_workspace(
    analyze_dataset: Callable[[Sequence[str]], DLSAnalysisResult],
    initial_paths: Sequence[str] = (),
    termination_callback: Callable[[], None] | None = None,
) -> None:
    application = NSApplication.sharedApplication()
    application.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = ApplicationDelegate.alloc().initWithTerminationCallback_(
        termination_callback
    )
    application.setDelegate_(delegate)

    style = (
        NSWindowStyleMaskTitled
        | NSWindowStyleMaskClosable
        | NSWindowStyleMaskMiniaturizable
        | NSWindowStyleMaskResizable
    )
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, 1380, 900), style, NSBackingStoreBuffered, False
    )
    window.setTitle_("LabAssistant")
    window.setMinSize_(NSMakeSize(1120, 740))
    window.center()

    configuration = WKWebViewConfiguration.alloc().init()
    controller = WorkspaceController.alloc().initWithAnalyzer_(analyze_dataset)
    configuration.userContentController().addScriptMessageHandler_name_(controller, "labassistant")
    webview = WKWebView.alloc().initWithFrame_configuration_(window.contentView().bounds(), configuration)
    webview.setAutoresizingMask_(18)
    webview.setNavigationDelegate_(controller)
    controller.webview = webview
    controller.pending_paths = tuple(initial_paths)
    window.setContentView_(webview)
    webview.loadHTMLString_baseURL_(WORKSPACE_HTML, NSURL.fileURLWithPath_("/"))
    window.makeKeyAndOrderFront_(None)
    application.activateIgnoringOtherApps_(True)
    signal_bridge = _AppSignalBridge(application)
    try:
        signal_bridge.start()
        application.run()
    finally:
        signal_bridge.close()

    # Retain native objects for the duration of the run loop.
    _ = (window, webview, controller, delegate)


class _AppSignalBridge:
    """Wake the Cocoa run loop when terminal signals arrive during objc calls."""

    def __init__(self, application) -> None:
        self.application = application
        self.signals = (signal.SIGINT, signal.SIGTERM)
        self.previous_handlers = {}
        self.previous_wakeup_fd = -1
        self.read_fd = -1
        self.write_fd = -1
        self.worker = None
        self.stopping = threading.Event()

    def start(self) -> None:
        self.read_fd, self.write_fd = os.pipe()
        os.set_blocking(self.read_fd, False)
        os.set_blocking(self.write_fd, False)
        self.previous_handlers = {
            signum: signal.getsignal(signum) for signum in self.signals
        }
        for signum in self.signals:
            signal.signal(signum, lambda signum, frame: None)
        self.previous_wakeup_fd = signal.set_wakeup_fd(self.write_fd)
        self.worker = threading.Thread(
            target=self._watch,
            name="labassistant-app-signal-bridge",
            daemon=True,
        )
        self.worker.start()

    def close(self) -> None:
        self.stopping.set()
        signal.set_wakeup_fd(self.previous_wakeup_fd)
        for signum, handler in self.previous_handlers.items():
            signal.signal(signum, handler)
        if self.write_fd >= 0:
            try:
                os.write(self.write_fd, b"\0")
            except OSError:
                pass
        if self.worker is not None:
            self.worker.join(0.5)
        for descriptor in (self.read_fd, self.write_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def _watch(self) -> None:
        while not self.stopping.is_set():
            readable, _, _ = select.select([self.read_fd], [], [], 0.5)
            if not readable:
                continue
            try:
                received = os.read(self.read_fd, 1024)
            except BlockingIOError:
                continue
            if not received or self.stopping.is_set():
                return
            run_loop = CFRunLoopGetMain()
            self.application.performSelectorOnMainThread_withObject_waitUntilDone_(
                "terminate:", None, False
            )
            CFRunLoopWakeUp(run_loop)
            return
