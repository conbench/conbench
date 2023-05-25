import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def remove_outliers_by_iqrdist(
    df: pd.DataFrame, colname: str, iqdistance=7, keep_last_n=2
) -> pd.DataFrame:
    """
    Inspect column `colname` for extreme outliers.

    Mutate input DataFrame `df` (side effect of this function!): replace
    outlier values in the specified column with NaN.

    Return a new DataFrame with only the outlier rows (before replacement),
    i.e. these rows contain the outlier values.

    The goal is to detect and throw out "obviously mismeasured data" (and of
    course this attempt is error-prone). Intended context: rough cleaning of
    _extreme_ outliers before doing linear regression.

    Method: measure distance from median in units of interquartile range (IQR):
    Remove individual data points that are more than iqdistance*IQR away from
    the median of all data points.

    The linear regression's goal is to provide the sign of a trend (increasing
    vs. decreasing), and to rank various time series against each other via a
    relative change metric derived from the linear regression.

    Bold idea: ignore the last N (tail end) data points. Towards the head/past
    end of the time series we do not want extreme outliers to impact the linear
    regression. The distribution of data obtained until today makes them likely
    to be actual outliers, they known to likely be more noise than signal. On
    the tail/fresh end however, "outliers" may be of a different cause, and
    this cause may also correspond to a different (higher) frequency of
    occurrence. These outliers _may_ be more signal than they are noise, and
    they should undergo human review, i.e. they should impact the linear
    regression.

    Of course if there have been outliers in the past then recent outliers are
    also likely to happen. They are even likely to be as of the same
    instability / methodological weakness in the underlying data acquisition
    method. In that sense, the asymmetrical data cleaning may even artificially
    emphasize (make the linear regression even _more_ prone to) recent
    outliers. But that's even a good idea I think! It's an additional motivator
    to improve the data acquisition method.

    Most importantly, this method does not exclusively emphasize recent
    outliers.

    So, this method absolutely over-emphasizes recent outliers but it also
    addresses the 'outliers in the past mess with everything' problem.

    In combination this is what we want: motivate to address _present_
    instabilities (make humans aware of current non-ideal data acquisition),
    and at the same deal with data from the past that was affected by
    instabilities that hopefully have been repaired by now.

    Concept used here: https://en.wikipedia.org/wiki/Interquartile_range

    I like this overview: https://stackoverflow.com/a/69001342

    Mutate input data frame (side effect of this function!): replace outlier
    values in the specified column with NaN.

    Return a DataFrame with only the outlier rows before replacement, i.e.
    these rows contain the outlier values.
    """
    assert len(df) > 5

    # df_sub = df[colname]
    df_sub = df.loc[:, colname]

    # Canonical interquartile range (IQR) calc.
    iqr = df_sub.quantile(0.75) - df_sub.quantile(0.25)

    # Build distance of each data point from median, in units of IQR. See if
    # this is larger than threshold `iqdistance`.
    outlier_index_mask = np.abs((df_sub - df_sub.median()) / iqr) > iqdistance

    # In the outlier mask, force the last two rows to be `False`. This is the
    # special treatment of the tail end (assume: most recent data) It's of
    # course interesting that we used these data points to calc median and iqr.
    outlier_index_mask.iloc[-keep_last_n:] = False
    # print(outlier_index_mask)

    # Prepare dataframe to return, with only the outlier data points.
    df_outliers = df.loc[outlier_index_mask]

    # if we mark more than 30 % of the data as outliers I don't think this is
    # cool, bail out. This kind of ignores when the input dataframe has many
    # NaNs.
    if float(len(df_outliers.index)) / len(df.index) > 0.2:
        log.warn("many outliers thrown out before lin reg:\n%s\n%s", df, df_outliers)

    # Mutate the input dataframe: set outliers to NaN.
    df.loc[outlier_index_mask, colname] = np.nan
    return df_outliers
