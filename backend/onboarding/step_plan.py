"""Works out which steps an onboarding contains, and in what order.

``OnboardingStep`` rows are shared templates, not per-onboarding rows: a step
applies to a role, to a set of services, or to everybody. The set of steps a
particular participant sees is therefore computed, and the "step 3 of 7"
number in the API is a position in that computed list -- it is deliberately
not ``OnboardingStep.display_order``, which is a global ordering hint.

Building a plan costs two queries regardless of how many steps exist, and
``build_step_plans`` builds plans for many onboardings in the same two. The
earlier per-step ``step.services.all()`` walk issued one query per step, per
onboarding, which is what made the admin changelist and the onboarding list
endpoint slow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Q

from onboarding.models import OnboardingStep

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


@dataclass(frozen=True)
class PlannedStep:
    """An ``OnboardingStep`` together with its position in one onboarding."""

    step: OnboardingStep
    number: int


class StepPlan:
    """The ordered steps of a single onboarding."""

    __slots__ = ("_by_id", "_by_number", "steps")

    def __init__(self, steps: Iterable[PlannedStep]) -> None:
        self.steps: tuple[PlannedStep, ...] = tuple(steps)
        self._by_id = {planned.step.id: planned.number for planned in self.steps}
        self._by_number = {planned.number: planned.step for planned in self.steps}

    def __len__(self) -> int:
        return len(self.steps)

    def __iter__(self) -> Iterator[PlannedStep]:
        return iter(self.steps)

    def __bool__(self) -> bool:
        return bool(self.steps)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    def number_for(self, step_id: int) -> int | None:
        """Position of a step in this plan, or ``None`` if it is not in it."""
        return self._by_id.get(step_id)

    def step_at(self, number: int) -> OnboardingStep | None:
        return self._by_number.get(number)

    def contains_step(self, step_id: int) -> bool:
        return step_id in self._by_id

    def step_ids(self) -> list[int]:
        return [planned.step.id for planned in self.steps]


def _visible_steps(roles: set[str]) -> list[OnboardingStep]:
    """Every step that could apply to any of ``roles``, services prefetched."""
    queryset = OnboardingStep.objects.filter(
        Q(onboarding_for__isnull=True)
        | Q(onboarding_for="")
        | Q(onboarding_for__in=roles)
    ).prefetch_related("services")
    return list(queryset.order_by("display_order", "id"))


def _plan_for(
    steps: list[OnboardingStep], role: str | None, service_ids: set[int]
) -> StepPlan:
    """Generic steps first, then the service-specific ones, numbered from 1."""
    generic: list[OnboardingStep] = []
    service_specific: list[OnboardingStep] = []

    for step in steps:
        if role and step.onboarding_for and step.onboarding_for != role:
            continue

        # `services` is prefetched, so this touches no database.
        step_service_ids = {service.id for service in step.services.all()}
        if not step_service_ids:
            generic.append(step)
        elif step_service_ids & service_ids:
            service_specific.append(step)

    ordered = generic + service_specific
    return StepPlan(
        PlannedStep(step=step, number=index) for index, step in enumerate(ordered, 1)
    )


def build_step_plan(onboarding) -> StepPlan:
    """The plan for one onboarding."""
    service_ids = set(onboarding.services.values_list("id", flat=True))
    roles = {onboarding.onboarding_for} if onboarding.onboarding_for else set()
    steps = _visible_steps(roles)
    return _plan_for(steps, onboarding.onboarding_for, service_ids)


def build_step_plans(onboardings) -> dict[int, StepPlan]:
    """Plans for many onboardings, keyed by onboarding id.

    Used by the onboarding list endpoint and the admin changelist, both of
    which need a step count for every row on the page.
    """
    onboardings = list(onboardings)
    if not onboardings:
        return {}

    roles = {ob.onboarding_for for ob in onboardings if ob.onboarding_for}
    steps = _visible_steps(roles)
    service_ids = _service_ids_by_onboarding(onboardings)

    return {
        ob.id: _plan_for(steps, ob.onboarding_for, service_ids[ob.id])
        for ob in onboardings
    }


def _service_ids_by_onboarding(onboardings) -> dict[int, set[int]]:
    """Read the Onboarding<->Service join table for many rows in one query."""
    from onboarding.models import Onboarding

    mapping: dict[int, set[int]] = {ob.id: set() for ob in onboardings}
    pairs = Onboarding.services.through.objects.filter(
        onboarding_id__in=list(mapping)
    ).values_list("onboarding_id", "service_id")

    for onboarding_id, service_id in pairs:
        mapping[onboarding_id].add(service_id)
    return mapping
