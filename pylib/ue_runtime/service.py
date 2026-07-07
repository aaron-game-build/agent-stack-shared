"""
Public service facade for task automation.

This is the stable Python API external tools should prefer. It composes the
registry, runtime context, runner, manifest, and policy gates behind one object.
"""

import os
from pathlib import Path

from ue_runtime.boundary import check_runtime_boundary
from ue_runtime.bundle import build_bundle_manifest, verify_bundle, write_bundle
from ue_runtime.context import RuntimeContext
from ue_runtime.advisor import group_report, health_report, recommend_tasks, safe_run_plan
from ue_runtime.install_audit import audit_runtime_install
from ue_runtime.install_plan import build_install_plan
from ue_runtime.installer import install_project
from ue_runtime.package import build_package_manifest
from ue_runtime.policy import evaluate_task_policy, policy_summary
from ue_runtime.protocol import build_service_descriptor
from ue_runtime.readiness import check_runtime_readiness
from ue_runtime.runner import TaskRunner
from ue_runtime.scaffold import build_project_scaffold
from ue_runtime.schemas import build_schema_document
from ue_runtime.smoke import run_runtime_smoke
from ue_runtime.validation import validate_registry, validate_registry_report


DEFAULT_REGISTRY_FACTORY = None  # projects bind via .ue-py-config.json task_runtime.registry_factory
REGISTRY_FACTORY_ENV = "UE_TASK_REGISTRY_FACTORY"
REPO_ROOT_ENV = "UE_TASK_REPO_ROOT"


def load_registry(factory_path):
    module_name, _, function_name = factory_path.partition(":")
    if not module_name or not function_name:
        raise ValueError("Registry factory must be in module:function form")
    module = __import__(module_name, fromlist=[function_name])
    factory = getattr(module, function_name)
    return factory()


class TaskService:
    def __init__(self, registry, context=None, registry_factory=None):
        self.registry = registry
        self.context = context
        self.registry_factory = registry_factory
        self.runner = TaskRunner(registry, context=context)

    @classmethod
    def from_factory(cls, factory_path=None, repo_root=None):
        context = RuntimeContext.from_repo_root(resolve_repo_root(repo_root))
        factory_path = resolve_registry_factory(context, explicit=factory_path)
        if not factory_path:
            raise ValueError(
                "No registry factory configured; set task_runtime.registry_factory in "
                ".ue-py-config.json or the %s env var" % REGISTRY_FACTORY_ENV
            )
        registry = load_registry(factory_path)
        return cls(registry, context=context, registry_factory=factory_path)

    def list_specs(self, kind=None, level=None, tag=None, max_risk=None, max_mode=None):
        specs = self.registry.list(kind=kind, level=level, tag=tag)
        if max_risk or max_mode:
            specs = [
                spec for spec in specs
                if self.gate(
                    spec.task_id,
                    max_risk=max_risk or "destructive",
                    max_mode=max_mode or "ue_pie",
                )["allowed"]
            ]
        return specs

    def list_tasks(self, **filters):
        return [spec.as_dict() for spec in self.list_specs(**filters)]

    def describe(self, task_id):
        return self.runner.describe(task_id)

    def plan(self, task_id):
        return self.runner.execution_plan(task_id)

    def command(self, task_id, max_risk=None, max_mode=None):
        if max_risk or max_mode:
            gate = self.gate(
                task_id,
                max_risk=max_risk or "destructive",
                max_mode=max_mode or "ue_pie",
            )
            if not gate["allowed"]:
                raise RuntimeError("Task %s denied by policy: %s" % (task_id, "; ".join(gate["reasons"])))
        return self.runner.command(task_id)

    def dry_run(self, task_id):
        return self.runner.dry_run(task_id)

    def run(self, task_id, allow_ue_process=False):
        return self.runner.run(task_id, allow_ue_process=allow_ue_process)

    def manifest(self, max_risk=None, max_mode=None):
        tasks = None
        if max_risk or max_mode:
            tasks = self.list_specs(max_risk=max_risk, max_mode=max_mode)
        return self.registry.manifest(
            context=self.context,
            registry_factory=self.registry_factory,
            tasks=tasks,
        )

    def policy_summary(self):
        return policy_summary(self.registry.list())

    def gate(self, task_id, max_risk="read_only", max_mode="local"):
        return evaluate_task_policy(self.registry.get(task_id), max_risk=max_risk, max_mode=max_mode)

    def validate(self, source_root=None):
        return validate_registry(self.registry, context=self.context, source_root=source_root)

    def validate_report(self, source_root=None):
        return validate_registry_report(self.registry, context=self.context, source_root=source_root)

    def readiness_report(self):
        return check_runtime_readiness(self)

    def boundary_report(self):
        return check_runtime_boundary()

    def descriptor(self):
        return build_service_descriptor(self)

    def schema(self, name="all"):
        return build_schema_document(name)

    def scaffold(self, project_name="ExampleProject", registry_module="project_tasks.registry", bootstrap_name="task.py"):
        return build_project_scaffold(
            project_name=project_name,
            registry_module=registry_module,
            bootstrap_name=bootstrap_name,
        )

    def package_manifest(self):
        return build_package_manifest()

    def install_plan(self, project_name="ExampleProject", registry_module="project_tasks.registry", bootstrap_name="task.py"):
        return build_install_plan(
            project_name=project_name,
            registry_module=registry_module,
            bootstrap_name=bootstrap_name,
        )

    def install_audit(self, target_root):
        return audit_runtime_install(target_root)

    def smoke(self, target_root=None):
        return run_runtime_smoke(self, target_root=target_root)

    def install(
        self,
        target_root,
        project_name="ExampleProject",
        registry_module="project_tasks.registry",
        bootstrap_name="task.py",
        apply=False,
        force=False,
        bundle_path=None,
        verify=False,
    ):
        return install_project(
            target_root,
            project_name=project_name,
            registry_module=registry_module,
            bootstrap_name=bootstrap_name,
            apply=apply,
            force=force,
            bundle_path=bundle_path,
            verify=verify,
        )

    def bundle_manifest(
        self,
        project_name="ExampleProject",
        registry_module="project_tasks.registry",
        bootstrap_name="task.py",
        include_scaffold=True,
    ):
        return build_bundle_manifest(
            project_name=project_name,
            registry_module=registry_module,
            bootstrap_name=bootstrap_name,
            include_scaffold=include_scaffold,
        )

    def bundle(
        self,
        output_path,
        project_name="ExampleProject",
        registry_module="project_tasks.registry",
        bootstrap_name="task.py",
        include_scaffold=True,
    ):
        return write_bundle(
            output_path,
            project_name=project_name,
            registry_module=registry_module,
            bootstrap_name=bootstrap_name,
            include_scaffold=include_scaffold,
        )

    def bundle_verify(self, bundle_path):
        return verify_bundle(bundle_path)

    def health(self, target_root=None):
        return health_report(self, target_root=target_root)

    def group(self, group, max_risk=None, max_mode=None):
        return group_report(self, group, max_risk=max_risk, max_mode=max_mode)

    def recommend(self, query, max_risk=None, max_mode=None, limit=10):
        return recommend_tasks(self, query, max_risk=max_risk, max_mode=max_mode, limit=limit)

    def safe_run_plan(self, task_id, max_risk="read_only", max_mode="local"):
        return safe_run_plan(self, task_id, max_risk=max_risk, max_mode=max_mode)


def _discover_repo_root():
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".ue-py-config.json").is_file():
            return candidate
    return here.parents[3]


def resolve_repo_root(explicit=None):
    if explicit:
        return explicit
    env_value = os.environ.get(REPO_ROOT_ENV)
    if env_value:
        return env_value
    return _discover_repo_root()


def resolve_registry_factory(context=None, explicit=None):
    if explicit:
        return explicit
    env_value = os.environ.get(REGISTRY_FACTORY_ENV)
    if env_value:
        return env_value
    if context:
        configured = context.task_registry_factory()
        if configured:
            return configured
    return DEFAULT_REGISTRY_FACTORY
