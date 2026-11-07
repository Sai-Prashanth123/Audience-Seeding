import pandas as pd

from seeding.seedmap import bait_factor, follower_band


def test_follower_band_prefers_mid_size():
    f = pd.Series([10, 50, 1_000, 50_000, 200_000, 5_000_000, None])
    b = follower_band(f).round(2).tolist()
    assert b[0] == 0.0 and b[1] == 0.0          # tiny accounts
    assert b[2] == 1.0 and b[3] == 1.0 and b[4] == 1.0
    assert b[5] == 0.3                          # mega accounts floor
    assert b[6] == 0.5                          # unknown


def test_bait_factor():
    s = pd.Series([0.0, 0.12, 0.26, 0.8, None])
    assert bait_factor(s).round(2).tolist() == [1.0, 1.0, 0.44, 0.1, 1.0]
