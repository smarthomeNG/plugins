"""The shipped huawei profiles are the import of the modbus_tcp huawei structs."""

import shutil

from plugins.modbus import profiles


def test_shipped_huawei_profiles_equal_an_import_of_the_modbus_tcp_structs(tmp_path):
    shutil.copytree(profiles.PROFILE_DIR / 'huawei', tmp_path / 'huawei')
    written = profiles.import_structs(profiles.modbus_tcp_structs('huawei'), 'huawei', tmp_path)
    assert sorted(path.name for path in written) == sorted(path.name for path in (tmp_path / 'huawei').iterdir())
    for path in written:
        assert path.read_text() == (profiles.PROFILE_DIR / 'huawei' / path.name).read_text(), path.name
