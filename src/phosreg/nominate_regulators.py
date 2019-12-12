from .classes import Clusters, ProteomicsData
from pandas import DataFrame
import scipy.stats
from itertools import product
from sklearn import linear_model
from typing import Iterable, Optional

reg_models = {
    'linear':linear_model.RidgeCV,
    'sigmoid':linear_model.LogisticRegressionCV
}


def notna(array):
    if isinstance(array, pd.Series):
        return ~array.isna()
    return ~np.isnan(array)


def corrNA(array1, array2):
    nonull = notna(array1) & notna(array2)
    return scipy.stats.pearsonr(array1[nonull], array2[nonull])


def collect_putative_regulators(protdata: ProteomicsData, put_reg_list) -> DataFrame:
    #TODO talk about how you don't want to use normalized data here, in docs
    subset = protdata.protein.loc[put_reg_list, :]
    ind2 = protdata.phospho.index.name[1]
    subset[ind2] = np.nan
    subset = subset.set_index(ind2, append=True)
    return subset.append(protdata.phospho.loc[put_reg_list, :])


def collapse_putative_regulators(reg_data: DataFrame, corr_threshold: float = 0.9) -> DataFrame:

    corr = {
        (ind1, ind2): corrNA(reg_data.loc[ind1, :], reg_data.loc[ind2, :])[0]
        for ind1, ind2 in product(reg_data.index, reg_data.index)
        if corrNA(reg_data.loc[ind1, :], reg_data.loc[ind2, :])[0] > corr_threshold
    }
    high_corr_inds = list(set([i[0] for i in corr.keys()]+[i[1] for i in corr.keys()]))
    low_corr_inds = reg_data.difference(high_corr_inds)
    grouped = reg_data.loc[low_corr_inds, :]

    while corr:
        for inds, corr in corr.items():
            name = tuple(['%s-%s' % (bit[0], bit[1]) for bit in zip(*inds)])
            grouped = grouped.append(pd.Series(reg_data.loc[list(inds),:].mean(), name=name))

        corr = {
            (ind1, ind2): corrNA(grouped.loc[ind1, :], grouped.loc[ind2, :])[0]
            for ind1, ind2 in product(grouped.index, grouped.index)
            if corrNA(grouped.loc[ind1, :], grouped.loc[ind2, :])[0] > corr_threshold
        }
        high_corr_inds = list(set([i[0] for i in corr.keys()] + [i[1] for i in corr.keys()]))
        low_corr_inds = reg_data.difference(high_corr_inds)
        grouped = grouped.loc[low_corr_inds, :]

    return grouped


def calculate_regulator_coefficients(
        reg_data: DataFrame,
        clusters: Clusters,
        model: str = 'sigmoid',
        regularization_values: Optional[Iterable] = [2 ** i for i in range(-10, 10, 1)],
        cv_fold: int = 5
) -> DataFrame:

    if model not in reg_models.keys():
        raise ValueError('Model %s not in accepted models: %s' % (model, ','.join(reg_models)))

    weights = pd.DataFrame()
    model = reg_models[model]
    model = model(regularization_values, cv=cv_fold)
    features = reg_data.transpose()
    targets = clusters.cluster_scores
    for col in targets:
        y = targets[col]
        model.fit(features, y)
        weights[col] = model.coef_
    return weights