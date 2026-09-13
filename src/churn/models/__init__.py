"""Gradient boosted model, its local explanation and its serialisation.

Three modules, three responsibilities, as listed in ``AGENTS.md`` section 7.

``train``
    Chooses the hyperparameters on the training rows alone and fits the model.
``explain``
    Turns native contributions into at most three business factors per account.
``registry``
    Saves and reloads a model with the metadata that makes it traceable.
"""
