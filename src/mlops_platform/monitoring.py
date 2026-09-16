"""Produce a reproducible drift snapshot from a controlled input shift."""

import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset
from evidently.ui.workspace import RemoteWorkspace
from sklearn.datasets import load_iris


def publish(base_url):
    iris = load_iris()
    reference = pd.DataFrame(iris.data, columns=iris.feature_names)
    current = reference.copy()
    current.iloc[:, 0] += 1.5
    snapshot = Report([DataDriftPreset()]).run(reference_data=reference, current_data=current)
    workspace = RemoteWorkspace(base_url)
    projects = workspace.search_project("Iris input monitoring")
    project = projects[0] if projects else workspace.create_project("Iris input monitoring")
    stored = workspace.add_run(project.id, snapshot)
    return {
        "project_id": str(project.id),
        "snapshot_id": str(stored.id),
        "scenario": "controlled +1.5 cm shift in sepal length; demonstration, not observed production drift",
    }
