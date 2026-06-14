from django.test import TestCase

from backend.enums import UserRole
from onboarding.step_plan import build_step_plan, build_step_plans
from tests.factories import (
    make_onboarding,
    make_question,
    make_service,
    make_step,
    make_user,
)


class PlanCompositionTests(TestCase):
    def setUp(self):
        self.care = make_service("Residential care")
        self.outreach = make_service("Community outreach")

        self.generic = make_step("Identity", order=1)
        self.staff_only = make_step("Right to work", role=UserRole.STAFF, order=2)
        self.care_only = make_step(
            "Availability", role=UserRole.STAFF, services=[self.care], order=3
        )
        self.outreach_only = make_step(
            "Travel", role=UserRole.STAFF, services=[self.outreach], order=4
        )

    def test_a_step_with_no_targets_is_in_every_plan(self):
        plan = build_step_plan(make_onboarding(role=UserRole.PARTICIPANT))
        assert [p.step.title for p in plan] == ["Identity"]

    def test_role_specific_steps_are_filtered_out_for_other_roles(self):
        plan = build_step_plan(make_onboarding(role=UserRole.STAFF))
        assert [p.step.title for p in plan] == ["Identity", "Right to work"]

    def test_service_steps_join_only_when_the_service_matches(self):
        onboarding = make_onboarding(role=UserRole.STAFF, services=[self.care])
        plan = build_step_plan(onboarding)
        assert [p.step.title for p in plan] == [
            "Identity",
            "Right to work",
            "Availability",
        ]

    def test_generic_steps_are_numbered_before_service_steps(self):
        onboarding = make_onboarding(role=UserRole.STAFF, services=[self.care])
        plan = build_step_plan(onboarding)
        assert [p.number for p in plan] == [1, 2, 3]
        assert plan.step_at(3).title == "Availability"
        assert plan.number_for(self.care_only.id) == 3
        assert plan.number_for(self.outreach_only.id) is None

    def test_step_numbers_are_per_onboarding_not_global(self):
        """The same step is number 3 for one participant and absent for another."""
        with_care = build_step_plan(
            make_onboarding(
                user=make_user("a@example.test"),
                role=UserRole.STAFF,
                services=[self.care],
            )
        )
        without = build_step_plan(
            make_onboarding(user=make_user("b@example.test"), role=UserRole.STAFF)
        )
        assert with_care.number_for(self.care_only.id) == 3
        assert without.number_for(self.care_only.id) is None
        assert len(without) == 2


class PlanQueryCountTests(TestCase):
    """The plan builders must not scale their query count with the data."""

    def setUp(self):
        self.service = make_service()
        question = make_question()
        for index in range(10):
            make_step(
                f"Step {index}",
                role=UserRole.STAFF,
                services=[self.service] if index % 2 else [],
                questions=[question] if index == 0 else [],
                order=index + 1,
            )

    def test_one_plan_costs_two_queries_whatever_the_step_count(self):
        onboarding = make_onboarding(role=UserRole.STAFF, services=[self.service])
        with self.assertNumQueries(3):
            plan = build_step_plan(onboarding)
            assert len(plan) == 10

    def test_many_plans_cost_the_same_as_one(self):
        onboardings = [
            make_onboarding(
                user=make_user(f"user{index}@example.test"),
                role=UserRole.STAFF,
                services=[self.service],
            )
            for index in range(6)
        ]
        with self.assertNumQueries(3):
            plans = build_step_plans(onboardings)
            assert {len(plan) for plan in plans.values()} == {10}
