"""
Security parity of the contribution / payment plans (reference data: no row scope).

- validateContributionPlanCode / validateContributionPlanBundleCode / validatePaymentPlanCode
  need the matching search right (they answered anyone, anonymous callers included).
- The update overrides look their target up through the row-security hook
  (core target_queryset via _target_queryset), never cls._model.objects.
"""
import json
from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from contribution_plan.apps import ContributionPlanConfig
from contribution_plan.gql.gql_mutations.contribution_plan_mutations import UpdateContributionPlanMutation
from contribution_plan.gql.gql_mutations.payment_plan_mutations import UpdatePaymentPlanMutation
from contribution_plan.models import ContributionPlan, PaymentPlan
from core.models.openimis_graphql_test_case import openIMISGraphQLTestCase
from core.test_helpers import create_right_only_user, get_test_token, perm_ids
from product.test_helpers import create_test_product

# any rule uuid: the plans are not calculated here (the module test helpers import a
# calculation rule this release does not ship)
CALCULATION = "11111111-2222-4333-8444-555555555555"


def _plan(model, user, code):
    product = create_test_product(code, custom_props={"insurance_period": 12})
    plan = model(code=code, name="before", benefit_plan_type=ContentType.objects.get(model="product"),
                 benefit_plan_id=product.id, periodicity=12, calculation=CALCULATION, json_ext={})
    plan.save(username=user.username)
    return plan


VALIDATIONS = (
    # query, argument, right
    ("validateContributionPlanCode", "contributionPlanCode",
     ContributionPlanConfig.gql_query_contributionplan_perms),
    ("validateContributionPlanBundleCode", "contributionPlanBundleCode",
     ContributionPlanConfig.gql_query_contributionplanbundle_perms),
    ("validatePaymentPlanCode", "paymentPlanCode",
     ContributionPlanConfig.gql_query_paymentplan_perms),
)


class ValidateCodeRightsTest(openIMISGraphQLTestCase):

    @classmethod
    def setUpTestData(cls):
        cls.tokens = {}
        for index, (query, _arg, perms) in enumerate(VALIDATIONS):
            user = create_right_only_user(f"cpspv{index}", perm_ids(perms))
            cls.tokens[query] = get_test_token(user)
        cls.no_right_token = get_test_token(create_right_only_user("cpspnone", []))

    def _q(self, query, token=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return json.loads(self.query(query, headers=headers).content)

    def _query(self, field, arg):
        return f'{{ {field}({arg}: "SP-NO-SUCH-CODE") }}'

    def test_anonymous_refused(self):
        for field, arg, _perms in VALIDATIONS:
            content = self._q(self._query(field, arg))
            self.assertIn("errors", content, f"{field}: {content}")
            self.assertIsNone((content.get("data") or {}).get(field), content)

    def test_without_the_search_right_refused(self):
        for field, arg, _perms in VALIDATIONS:
            content = self._q(self._query(field, arg), self.no_right_token)
            self.assertIn("errors", content, f"{field}: {content}")
            self.assertIsNone((content.get("data") or {}).get(field), content)

    def test_another_plan_right_is_not_enough(self):
        # the contribution plan right does not open the payment plan oracle
        content = self._q(self._query("validatePaymentPlanCode", "paymentPlanCode"),
                          self.tokens["validateContributionPlanCode"])
        self.assertIn("errors", content, content)

    def test_with_the_search_right(self):
        for field, arg, _perms in VALIDATIONS:
            content = self._q(self._query(field, arg), self.tokens[field])
            self.assertNotIn("errors", content, f"{field}: {content}")
            self.assertTrue(content["data"][field], content)


class UpdateTargetLookupTest(TestCase):
    """The update looks its target up through _target_queryset (row security), so a row
    the hook leaves out is not updated."""

    @classmethod
    def setUpTestData(cls):
        from core.models import User
        cls.user = User.objects.filter(username="Admin").first() or \
            User.objects.create_superuser(username="Admin", password="S\\/pe®Pąßw0rd™")
        cls.cp = _plan(ContributionPlan, cls.user, "SPCP1")
        cls.pp = _plan(PaymentPlan, cls.user, "SPPP1")

    def _update_hidden(self, mutation, model, obj):
        hidden = mock.Mock(return_value=model.objects.none())
        with mock.patch.object(mutation, "_target_queryset", hidden):
            errors = mutation.async_mutate(self.user, id=str(obj.id), code=obj.code, name="after",
                                           calculation=str(obj.calculation), periodicity=obj.periodicity,
                                           benefit_plan_type="product", benefit_plan_id=obj.benefit_plan_id)
        hidden.assert_called()
        self.assertTrue(errors, errors)
        self.assertEqual("before", model.objects.get(id=obj.id).name)

    def test_contribution_plan_out_of_reach_not_updated(self):
        self._update_hidden(UpdateContributionPlanMutation, ContributionPlan, self.cp)

    def test_payment_plan_out_of_reach_not_updated(self):
        self._update_hidden(UpdatePaymentPlanMutation, PaymentPlan, self.pp)

    def test_contribution_plan_in_reach_updated(self):
        errors = UpdateContributionPlanMutation.async_mutate(
            self.user, id=str(self.cp.id), name="after", calculation=str(self.cp.calculation),
            periodicity=self.cp.periodicity, benefit_plan_type="product", benefit_plan_id=self.cp.benefit_plan_id)
        self.assertFalse(errors, errors)
        self.assertEqual("after", ContributionPlan.objects.get(id=self.cp.id).name)
