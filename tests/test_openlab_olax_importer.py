import zipfile
from pathlib import Path

from labassistant.importers.openlab_olax import inspect_openlab_olax, parser_report


def make_olax(path: Path) -> None:
    sequence_xml = """
    <Sequence>
      <SequenceName>Mass balance run</SequenceName>
      <Operator>MT</Operator>
      <Injection>
        <InjectionOrder>1</InjectionOrder>
        <SampleName>Blank 1</SampleName>
        <Method>HPLC_Method_A</Method>
        <RunTimeMin>12.5</RunTimeMin>
      </Injection>
      <Injection>
        <InjectionOrder>2</InjectionOrder>
        <SampleName>Standard 1</SampleName>
        <Method>HPLC_Method_A</Method>
        <RunTimeMin>12.5</RunTimeMin>
      </Injection>
      <Injection>
        <InjectionOrder>3</InjectionOrder>
        <SampleName>Sample A</SampleName>
        <Method>HPLC_Method_A</Method>
        <RunTimeMin>12.5</RunTimeMin>
      </Injection>
    </Sequence>
    """
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Sequence/sequence.xml", sequence_xml)
        archive.writestr("Data/Injection_001/signal.ch", "time_min,intensity\n0.0,10\n0.5,15\n1.0,12\n")
        archive.writestr("Data/Injection_002/signal.ch", "time_min,intensity\n0.0,20\n0.5,25\n1.0,22\n")
        archive.writestr("Data/Injection_003/signal.ch", "time_min,intensity\n0.0,30\n0.5,35\n1.0,32\n")
        archive.writestr("Results/peak_table.csv", "sample,peak,area\nSample A,parent,1000\n")


def test_inspect_openlab_olax_extracts_archive_metadata(tmp_path):
    fixture = tmp_path / "HPLC Test.olax"
    make_olax(fixture)

    result = inspect_openlab_olax(fixture)

    assert result.is_zip is True
    assert len(result.archive_entries) == 5
    assert result.sequence_metadata["sequence_name"] == "Mass balance run"
    assert result.sequence_metadata["operator"] == "MT"
    assert [injection.sample_name for injection in result.injections] == ["Blank 1", "Standard 1", "Sample A"]
    assert result.injections[2].injection_order == 3
    assert result.injections[2].method == "HPLC_Method_A"
    assert result.injections[2].run_time_min == 12.5
    assert len(result.signal_files) == 3
    assert result.peak_table_files == ["Results/peak_table.csv"]
    assert len(result.measurements) == 3
    assert result.measurements[2].sample_name == "Sample A"
    assert result.measurements[2].peaks[0].name == "parent"
    assert result.measurements[2].peaks[0].role == "parent"
    assert result.measurements[2].total_area == 1000
    assert result.measurements[0].metadata["openlab_signal_files"] == ["Data/Injection_001/signal.ch"]
    assert result.measurements[1].metadata["openlab_signal_files"] == ["Data/Injection_002/signal.ch"]
    assert result.measurements[2].metadata["openlab_signal_files"] == ["Data/Injection_003/signal.ch"]
    assert len(result.decoded_signal_traces) == 3
    assert result.unsupported_signal_files == []
    assert len(result.measurements[2].chromatogram_traces) == 1
    trace = result.measurements[2].chromatogram_traces[0]
    assert trace.source_file == "Data/Injection_003/signal.ch"
    assert trace.time_min == [0.0, 0.5, 1.0]
    assert trace.intensity == [30.0, 35.0, 32.0]
    assert len(trace.time_min) == len(trace.intensity)
    assert trace.time_min == sorted(trace.time_min)


def test_openlab_olax_generates_import_observations(tmp_path):
    fixture = tmp_path / "HPLC Test.olax"
    make_olax(fixture)

    result = inspect_openlab_olax(fixture)
    labels = [observation.label for observation in result.observations]

    assert "OpenLab sequence loaded" in labels
    assert "Injections found" in labels
    assert "Blanks/standards/samples identified" in labels
    assert "Chromatogram signal available" in labels
    assert "Chromatogram trace decoded" in labels
    assert "Missing peak table" not in labels
    assert "Peak table available" in labels


def test_openlab_olax_reports_missing_peak_table(tmp_path):
    fixture = tmp_path / "No Results.olax"
    with zipfile.ZipFile(fixture, "w") as archive:
        archive.writestr("sequence.csv", "sample_name,injection_number,method,run_time_min\nSample A,1,M,5.5\n")
        archive.writestr("data/signal_001.ch", b"raw")

    result = inspect_openlab_olax(fixture)
    report = parser_report(fixture)

    assert [injection.sample_name for injection in result.injections] == ["Sample A"]
    assert result.measurements[0].method_name == "M"
    assert result.decoded_signal_traces == []
    assert result.measurements[0].chromatogram_traces == []
    assert result.unsupported_signal_files == ["data/signal_001.ch"]
    assert "Missing peak table" in [observation.label for observation in result.observations]
    assert "Peak/result files: none found" in report


def test_openlab_olax_reads_realistic_nested_result_package(tmp_path):
    fixture = tmp_path / "Realistic.olax"
    prefix = "1290+HPLC-2026-07-02+12-23-00-04-00.rslt%5c"
    acaml = """
    <ACAML>
      <Doc>
        <DocInfo>
          <Description>1290 HPLC-2026-07-02 12-23-00-04-00</Description>
          <CreatedByUser>admin</CreatedByUser>
          <CreationDate>2026-07-02T16:23:00Z</CreationDate>
          <ClientName>OBM-NH-INST-02</ClientName>
          <CustomField Name="InjectionMetaDataItems">
            <Xml>
              <ArrayOfInjectionMetaData>
                <InjectionMetaData InjectionId="1" SampleName="Blank" AcqMethodName="Phenyl Hexyl column 50C" InjectionAcqDateTime="2026-07-02T16:23:50Z" />
                <InjectionMetaData InjectionId="2" SampleName="Standard" AcqMethodName="Phenyl Hexyl column 50C" InjectionAcqDateTime="2026-07-02T16:52:55Z" />
              </ArrayOfInjectionMetaData>
            </Xml>
          </CustomField>
        </DocInfo>
      </Doc>
    </ACAML>
    """
    rx_payload = tmp_path / "rx.zip"
    with zipfile.ZipFile(rx_payload, "w") as rx:
        rx.writestr("Base/AuditTrail", b"Acquisition started for injection 1")
        rx.writestr("Base/InjectionACAML", """
        <Injection>
          <InjectionId>1</InjectionId>
          <SampleName>Blank</SampleName>
          <AcqMethodName>Phenyl Hexyl column 50C</AcqMethodName>
        </Injection>
        """)
    dx_payload = tmp_path / "dx.zip"
    with zipfile.ZipFile(dx_payload, "w") as dx:
        dx.writestr("[Content_Types].xml", "<Types />")
        dx.writestr("Base/Signal", "time_min,response\n0.0,100\n0.25,125\n0.50,110\n")
    sqx_payload = tmp_path / "sqx.zip"
    with zipfile.ZipFile(sqx_payload, "w") as sqx:
        sqx.writestr("SampleListPart/SampleListPart", "<SampleList />")
    amx_payload = tmp_path / "amx.zip"
    with zipfile.ZipFile(amx_payload, "w") as amx:
        amx.writestr("Agilent/MethodType", b"method")

    with zipfile.ZipFile(fixture, "w") as archive:
        archive.writestr(prefix + "1290+HPLC-2026-07-02+12-23-00-04-00.acaml", acaml)
        archive.writestr(prefix + "1290+HPLC-2026-07-02+12-23-00-04-00.mfx", "<Fileset />")
        archive.write(rx_payload, prefix + "2026-07-02+12-23-03-04-00-01.rx")
        archive.write(dx_payload, prefix + "2026-07-02+12-23-03-04-00-01.dx")
        archive.write(sqx_payload, prefix + "7-2-26+Phenyl-hexyl+column+test+1.sqx")
        archive.write(amx_payload, prefix + "Phenyl+Hexyl+column+50C.amx")
        archive.writestr("[Content_Types].xml", "<Types />")

    result = inspect_openlab_olax(fixture)

    assert [injection.sample_name for injection in result.injections] == ["Blank", "Standard"]
    assert [injection.injection_order for injection in result.injections] == [1, 2]
    assert result.signal_files == [
        "1290+HPLC-2026-07-02+12-23-00-04-00.rslt%5c2026-07-02+12-23-03-04-00-01.dx"
    ]
    assert result.detector_files == result.signal_files
    assert result.acquisition_method_files
    assert result.audit_files
    assert result.measurements[0].metadata["openlab_signal_files"] == result.signal_files
    assert len(result.decoded_signal_traces) == 1
    assert result.decoded_signal_traces[0].metadata["payload_path"] == "Base/Signal"
    assert result.decoded_signal_traces[0].time_min == [0.0, 0.25, 0.5]
    assert result.decoded_signal_traces[0].intensity == [100.0, 125.0, 110.0]
    assert result.measurements[0].chromatogram_traces == result.decoded_signal_traces
    assert result.measurements[1].chromatogram_traces == []
    labels = [observation.label for observation in result.observations]
    assert "Chromatogram signal available" in labels
    assert "Chromatogram trace decoded" in labels
    assert "Acquisition method available" in labels
    assert "Audit trail available" in labels


def test_openlab_olax_uses_raw_data_filename_for_guid_injection_order(tmp_path):
    fixture = tmp_path / "Guid Order.olax"
    acaml = """
    <ACAML>
      <InjectionMetaData
        InjectionId="0ed54be7-8ef9-4d0e-8740-3a353d0a2816"
        SampleName="Blank"
        AcqMethodName="Method A"
        InjectionAcqDateTime="2026-07-02T16:23:50.175Z"
        RawDataFileName="2026-07-02 12-23-03-04-00-01.dx" />
      <SampleContainerInfo>
        <Name>Sampler</Name>
      </SampleContainerInfo>
    </ACAML>
    """
    with zipfile.ZipFile(fixture, "w") as archive:
        archive.writestr("Run.rslt%5cRun.acaml", acaml)
        archive.writestr("Run.rslt%5c2026-07-02+12-23-03-04-00-01.dx", b"PK")

    result = inspect_openlab_olax(fixture)

    assert len(result.injections) == 1
    assert result.injections[0].sample_name == "Blank"
    assert result.injections[0].injection_order == 1
    assert result.injections[0].raw_data_file == "2026-07-02 12-23-03-04-00-01.dx"
    assert result.injections[0].measurement_datetime == "2026-07-02T16:23:50.175Z"


def test_openlab_olax_handles_unavailable_file(tmp_path):
    missing = tmp_path / "missing.olax"

    result = inspect_openlab_olax(missing)

    assert result.is_zip is False
    assert result.errors == ["File does not exist."]
    assert result.measurements == []
