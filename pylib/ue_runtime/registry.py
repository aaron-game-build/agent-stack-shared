"""
Task registry for automation metadata.

Project code owns registration. Runtime code owns validation, lookup, filtering,
and stable listing behavior.
"""

from collections import OrderedDict

from ue_runtime.manifest import build_manifest


class TaskRegistry:
    def __init__(self):
        self._tasks = OrderedDict()

    def register(self, spec):
        spec.validate()
        if spec.task_id in self._tasks:
            raise ValueError("Duplicate task id: %s" % spec.task_id)
        self._tasks[spec.task_id] = spec
        return spec

    def register_many(self, specs):
        for spec in specs:
            self.register(spec)
        return self

    def get(self, task_id):
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError("Unknown task id: %s" % task_id)

    def list(self, kind=None, level=None, tag=None):
        tasks = list(self._tasks.values())
        if kind:
            tasks = [task for task in tasks if task.kind == kind]
        if level:
            tasks = [task for task in tasks if task.level == level]
        if tag:
            tasks = [task for task in tasks if tag in task.tags]
        return tasks

    def ids(self):
        return list(self._tasks.keys())

    def manifest(self, context=None, registry_factory=None, tasks=None):
        return build_manifest(self, context=context, registry_factory=registry_factory, tasks=tasks)

    def __contains__(self, task_id):
        return task_id in self._tasks

    def __len__(self):
        return len(self._tasks)
