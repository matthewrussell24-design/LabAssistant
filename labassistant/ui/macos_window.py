"""Native AppKit window hosting the local LabAssistant research workspace."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

import objc
from AppKit import (
    NSApp,
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
from WebKit import WKWebView, WKWebViewConfiguration

from labassistant.application import DLSAnalysisResult
from labassistant.ui.presenters import result_payload
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

    def webView_didFinishNavigation_(self, webview, navigation):
        if self.pending_paths:
            paths = self.pending_paths
            self.pending_paths = ()
            self.analyzePaths_(paths)

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
    def applicationShouldTerminateAfterLastWindowClosed_(self, application):
        return True


def run_native_workspace(
    analyze_dataset: Callable[[Sequence[str]], DLSAnalysisResult],
    initial_paths: Sequence[str] = (),
) -> None:
    application = NSApplication.sharedApplication()
    application.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = ApplicationDelegate.alloc().init()
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
    application.run()

    # Retain native objects for the duration of the run loop.
    _ = (window, webview, controller, delegate)
