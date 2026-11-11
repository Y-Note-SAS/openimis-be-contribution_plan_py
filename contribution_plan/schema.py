import graphene
import graphene_django_optimizer as gql_optimizer

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.translation import gettext as _

from core.schema import signal_mutation_module_validate
from contribution_plan.gql import ContributionPlanGQLType, ContributionPlanBundleGQLType, \
    ContributionPlanBundleDetailsGQLType, PaymentPlanGQLType
from contribution_plan.services import \
    ContributionPlanService, ContributionPlanBundleService, PaymentPlan as PaymentPlanService
from core.utils import append_validity_filter
from contribution_plan.gql.gql_mutations.contribution_plan_bundle_details_mutations import \
    CreateContributionPlanBundleDetailsMutation, UpdateContributionPlanBundleDetailsMutation, \
    DeleteContributionPlanBundleDetailsMutation, ReplaceContributionPlanBundleDetailsMutation
from contribution_plan.gql.gql_mutations.contribution_plan_bundle_mutations import CreateContributionPlanBundleMutation, \
    UpdateContributionPlanBundleMutation, DeleteContributionPlanBundleMutation, ReplaceContributionPlanBundleMutation
from contribution_plan.gql.gql_mutations.contribution_plan_mutations import CreateContributionPlanMutation, \
    UpdateContributionPlanMutation, DeleteContributionPlanMutation, ReplaceContributionPlanMutation
from contribution_plan.gql.gql_mutations.payment_plan_mutations import CreatePaymentPlanMutation, \
    UpdatePaymentPlanMutation, DeletePaymentPlanMutation, ReplacePaymentPlanMutation
from contribution_plan.models import ContributionPlanBundle, ContributionPlan, \
    ContributionPlanBundleDetails, PaymentPlan
from core.schema import OrderedDjangoFilterConnectionField
from .models import ContributionPlanMutation, ContributionPlanBundleMutation
from .apps import ContributionPlanConfig


def _check_query_perms(info, perms):
    """The search right (an anonymous caller holds none)."""
    user = info.context.user
    if user is None or getattr(user, "is_anonymous", True) or not user.has_perms(perms):
        raise PermissionDenied(_("unauthorized"))


class Query(graphene.ObjectType):
    contribution_plan = OrderedDjangoFilterConnectionField(
        ContributionPlanGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        showHistory=graphene.Boolean()
    )

    contribution_plan_bundle = OrderedDjangoFilterConnectionField(
        ContributionPlanBundleGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        calculation=graphene.UUID(),
        insuranceProduct=graphene.Int(),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        showHistory=graphene.Boolean(),
        clientMutationId=graphene.String()
    )

    contribution_plan_bundle_details = OrderedDjangoFilterConnectionField(
        ContributionPlanBundleDetailsGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean()
    )

    payment_plan = OrderedDjangoFilterConnectionField(
        PaymentPlanGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        dateValidFrom__Gte=graphene.DateTime(),
        dateValidTo__Lte=graphene.DateTime(),
        applyDefaultValidityFilter=graphene.Boolean(),
        showHistory=graphene.Boolean()
    )

    validate_contribution_plan_code = graphene.Field(
        graphene.Boolean,
        contribution_plan_code=graphene.String(required=True),
        description="Checks that the specified contribution plan code is unique."
    )

    validate_payment_plan_code = graphene.Field(
        graphene.Boolean,
        payment_plan_code=graphene.String(required=True),
        description="Check that the specified payment plan code is unique"
    )

    validate_contribution_plan_bundle_code = graphene.Field(
        graphene.Boolean,
        contribution_plan_bundle_code=graphene.String(required=True),
        description="Checks that the specified contribution plan bundle code is unique."
    )

    def resolve_contribution_plan(self, info, **kwargs):
        if not info.context.user.has_perms(ContributionPlanConfig.gql_query_contributionplan_perms):
           raise PermissionError("Unauthorized")

        filters = append_validity_filter(**kwargs)
        model = ContributionPlan
        if kwargs.get('showHistory', False):
            query = model.history.filter(*filters).all().as_instances()
        else:
            query = model.objects.filter(*filters).all()
        return gql_optimizer.query(query, info)

    def resolve_contribution_plan_bundle(self, info, **kwargs):
        if not info.context.user.has_perms(ContributionPlanConfig.gql_query_contributionplanbundle_perms):
            raise PermissionError("Unauthorized")

        filters = append_validity_filter(**kwargs)

        calculation = kwargs.get('calculation', None)
        insurance_product = kwargs.get('insuranceProduct', None)

        show_history = kwargs.get('showHistory')
        model = ContributionPlanBundle

        client_mutation_id = kwargs.pop("clientMutationId", None)
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        if show_history:
            query = model.history.filter(*filters).all().as_instances()
        else:
            query = model.objects.filter(*filters).all()


        if show_history and (calculation or insurance_product):
            filtered_details = ContributionPlanBundleDetails.objects
            if calculation:
                filtered_details = filtered_details.filter(
                    contribution_plan__calculation=str(calculation)
                ).values_list('contribution_plan_bundle', flat=True)
            if insurance_product:
                filtered_details = filtered_details.filter(
                    contribution_plan__benefit_plan__id=insurance_product
                ).values_list('contribution_plan_bundle', flat=True)
            query = query.filter(id__in=filtered_details)
        else:
            if calculation:
                query = query.filter(
                    contributionplanbundledetails__contribution_plan__calculation=str(calculation)
                ).distinct()
            if insurance_product:
                query = query.filter(
                    contributionplanbundledetails__contribution_plan__benefit_plan__id=insurance_product
                ).distinct()


        return gql_optimizer.query(query.filter(*filters).all(), info)

    def resolve_contribution_plan_bundle_details(self, info, **kwargs):
        if not (info.context.user.has_perms(
                ContributionPlanConfig.gql_query_contributionplanbundle_perms) and info.context.user.has_perms(
                ContributionPlanConfig.gql_query_contributionplan_perms)):
           raise PermissionError("Unauthorized")
        filters = append_validity_filter(**kwargs)
        query = ContributionPlanBundleDetails.objects
        return gql_optimizer.query(query.filter(*filters).all(), info)

    def resolve_payment_plan(self, info, **kwargs):
        if not info.context.user.has_perms(ContributionPlanConfig.gql_query_paymentplan_perms):
           raise PermissionError("Unauthorized")

        filters = append_validity_filter(**kwargs)
        model = PaymentPlan
        if kwargs.get('showHistory', False):
            query = model.history.filter(*filters).all().as_instances()
        else:
            query = model.objects.filter(*filters).all()
        return gql_optimizer.query(query, info)

    def resolve_validate_contribution_plan_code(self, info, **kwargs):
        # a code oracle for the users who may search the plans only
        _check_query_perms(info, ContributionPlanConfig.gql_query_contributionplan_perms)
        errors = ContributionPlanService.check_unique_code(code=kwargs['contribution_plan_code'])
        return False if errors else True

    def resolve_validate_contribution_plan_bundle_code(self, info, **kwargs):
        _check_query_perms(info, ContributionPlanConfig.gql_query_contributionplanbundle_perms)
        errors = ContributionPlanBundleService.check_unique_code(code=kwargs['contribution_plan_bundle_code'])
        return False if errors else True

    def resolve_validate_payment_plan_code(self, info, **kwargs):
        _check_query_perms(info, ContributionPlanConfig.gql_query_paymentplan_perms)
        errors = PaymentPlanService.check_unique_code(code=kwargs['payment_plan_code'])
        return False if errors else True


class Mutation(graphene.ObjectType):
    create_contribution_plan_bundle = CreateContributionPlanBundleMutation.Field()
    create_contribution_plan = CreateContributionPlanMutation.Field()
    create_contribution_plan_bundle_details = CreateContributionPlanBundleDetailsMutation.Field()
    create_payment_plan = CreatePaymentPlanMutation.Field()
    
    update_contribution_plan_bundle = UpdateContributionPlanBundleMutation.Field()
    update_contribution_plan = UpdateContributionPlanMutation.Field()
    update_contribution_plan_bundle_details = UpdateContributionPlanBundleDetailsMutation.Field()
    update_payment_plan = UpdatePaymentPlanMutation.Field()
    
    delete_contribution_plan_bundle = DeleteContributionPlanBundleMutation.Field()
    delete_contribution_plan = DeleteContributionPlanMutation.Field()
    delete_contribution_plan_bundle_details = DeleteContributionPlanBundleDetailsMutation.Field()
    delete_payment_plan = DeletePaymentPlanMutation.Field()

    replace_contribution_plan_bundle = ReplaceContributionPlanBundleMutation.Field()
    replace_contribution_plan = ReplaceContributionPlanMutation.Field()
    replace_contribution_plan_bundle_details = ReplaceContributionPlanBundleDetailsMutation.Field()
    replace_payment_plan = ReplacePaymentPlanMutation.Field()


def on_contribution_plan_mutation(sender, **kwargs):
    uuid = kwargs['data'].get('uuid', None)
    if not uuid:
        return []
    if "ContributionPlanMutation" in str(sender._mutation_class):
        impacted_contribution_plan = ContributionPlan.objects.get(id=uuid)
        ContributionPlanMutation.objects.create(
            contribution_plan=impacted_contribution_plan, mutation_id=kwargs['mutation_log_id'])
    if "ContributionPlanBundleMutation" in str(sender._mutation_class):
        impacted_contribution_plan_bundle = ContributionPlanBundle.objects.get(id=uuid)
        ContributionPlanBundleMutation.objects.create(
            contribution_plan_bundle=impacted_contribution_plan_bundle, mutation_id=kwargs['mutation_log_id'])
    return []


def bind_signals():
    signal_mutation_module_validate["contribution_plan"].connect(on_contribution_plan_mutation)
