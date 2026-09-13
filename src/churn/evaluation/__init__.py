"""Evaluation protocol, built before any model on purpose.

A protocol written after seeing a model's results bends towards them. This
package is therefore complete, measured on the baselines, before lot 5 trains a
single tree.

``splitting``
    Chronological folds with an embargo and a purge, decision D4.
``metrics``
    Precision@K per scoring period, recall at K, lift, decision D5.
``baselines``
    Random ranking, revenue ranking and a regularised logistic regression.
``protocol``
    Runs any scorer through the folds and gathers the measures.
``report``
    Writes the results, always stating the data source, decision D2.
"""

__all__: list[str] = []
