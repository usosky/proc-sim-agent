"""tools/scrub_aspen_files.py: what is removed, what is kept."""
import scrub_aspen_files as scrub


def test_licence_and_paths_removed_in_text_files():
    text = (" THIS COPY OF ASPEN PLUS LICENSED TO ACME TEST CORP     \r\n"
            " LOCATED IN: C:\\Program Files\\AspenTech\\Aspen Plus V15.0\\Engine\\xeq\r\n"
            " LOCATED IN:                    \r\n"
            "          3    ;Directory C:\\Users\\jdoe\\sims  Runid MODEL\r\n"
            "          3    ;Directory   Runid MODEL\r\n"
            " INSTALLATION:                                           11:02:41 P.M.\r\n"
            " INSTALLATION: ACME SITE 3                               11:02:41 P.M.\r\n")
    new, changes = scrub.scrub_text(text, ".his")
    assert "ACME" not in new and "jdoe" not in new and "Program Files" not in new
    assert "Runid MODEL" in new                       # the run id stays
    assert "11:02:41 P.M." in new                     # the time column stays
    assert " LOCATED IN:                    \r\n" in new  # blank value untouched
    assert new.count("\r\n") == text.count("\r\n")    # line endings kept
    assert len(changes) == 4  # licence, install path, run folder, installation site


def test_backup_lines_keep_their_length():
    vers = ' DSET RUN-STATUS VERS @VERS ( "39.0" "WIN-X64" "" "jdoe" "DESKTOP-ABC123" )    \r\n'
    comment = '";Directory E:\\proj\\sim  Filename E:\\proj\\sim\\model" \r\n'
    new, changes = scrub.scrub_text(vers + comment, ".bkp")
    a, b = new.split("\r\n")[:2]
    assert '"" "" )' in a and "jdoe" not in a and "DESKTOP" not in a
    assert "proj" not in b
    assert len(a) == len(vers) - 2 and len(b) == len(comment) - 2
    assert len(changes) == 2


def test_suspects_skip_encoded_blocks_but_flag_paths():
    encoded = '"@UYX<C51FBICFL8>m\\@00`WOP62@@0=oh2k3P@020DP0@06mJVC0U=2<RB=?D1X<PTACC9XbYjSe6Se6" '
    assert scrub.suspects(encoded) == []
    assert scrub.suspects("  EXCEL FILE C:\\Users\\jdoe\\calc.xlsx")
    assert scrub.suspects("  contact jdoe@example.com")


def test_cli_check_and_out(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    (src / "m.his").write_bytes(b" THIS COPY OF ASPEN PLUS LICENSED TO ACME\r\n")
    assert scrub.main([str(src), "--check"]) == 1
    out = tmp_path / "out"
    assert scrub.main([str(src), "--out", str(out)]) == 0
    assert scrub.main([str(out), "--check"]) == 0
    assert (src / "m.his").read_bytes() == b" THIS COPY OF ASPEN PLUS LICENSED TO ACME\r\n"  # original untouched


def test_wrapped_vers_record_is_scrubbed_with_lengths_kept():
    text = (' DSET RUN-STATUS VERS @VERS ( "39.0" "WIN-X64" "" "averyveryverylongusername"\r\n'
            ' "DESKTOP-ABCDEFGHIJK" )                                                   \r\n')
    new, changes = scrub.scrub_text(text, ".bkp")
    assert "averyvery" not in new and "DESKTOP" not in new
    assert [len(x) for x in new.split("\n")] == [len(x) for x in text.split("\n")]
    assert changes and "wrapped" in changes[0]


def test_cli_keeps_subfolders_and_survives_cp1252_console(tmp_path):
    import os
    import subprocess
    import sys
    from conftest import ROOT
    src = tmp_path / "in"
    for v in ("v1", "v2"):
        (src / v).mkdir(parents=True)
        (src / v / "m.his").write_bytes(b" THIS COPY OF ASPEN PLUS LICENSED TO ACME\r\n odd byte \x96 C:\\Users\\jdoe\\x\r\n")
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "scrub_aspen_files.py"), str(src), "--out",
                        str(tmp_path / "out")], capture_output=True, env=env, timeout=60)
    assert p.returncode == 0, p.stderr
    assert b"Traceback" not in p.stderr
    assert (tmp_path / "out" / "v1" / "m.his").exists() and (tmp_path / "out" / "v2" / "m.his").exists()
