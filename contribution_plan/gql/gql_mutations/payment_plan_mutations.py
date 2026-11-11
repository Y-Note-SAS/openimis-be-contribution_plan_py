from django.contrib.contenttypes.models import ContentType

from core.gql.gql_mutations import DeleteInputType
from core.gql.gql_mutations.base_mutation import BaseMutation, BaseDeleteMutation, BaseReplaceMutation, \
    BaseHistoryModelCreateMutationMixin, BaseHistoryModelUpdateMutationMixin, \
    BaseHistoryModelDeleteMutationMixin, BaseHistoryModelReplaceMutationMixin
from contribution_plan.services import PaymentPlan as PaymentPlanService
from contribution_plan.gql.gql_mutations import PaymentPlanInputType, PaymentPlanUpdateInputType, \
    PaymentPlanReplaceInputType
from contribution_plan.apps import ContributionPlanConfig
from contribution_plan.models import PaymentPlan
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CreatePaymentPlanMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "PaymentPlanMutation"
    _mutation_module = "contribution_plan"
    _model = PaymentPlan

    @classmethod
    def create_object(cls, user, object_data):
        content_type = ContentType.objects.get(model=object_data['benefit_plan_type'].lower())
        object_data['benefit_plan_type'] = content_type
        obj = cls._model(**object_data)
        obj.save(username=user.username)
        return obj

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                ContributionPlanConfig.gql_mutation_create_paymentplan_perms):
            raise ValidationError(_("mutation.authentication_required"))
        if PaymentPlanService.check_unique_code(data['code']):
            raise ValidationError(_("mutation.payment_plan_code_duplicated"))

    class Input(PaymentPlanInputType):
        pass


class UpdatePaymentPlanMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "PaymentPlanMutation"
    _mutation_module = "contribution_plan"
    _model = PaymentPlan

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                ContributionPlanConfig.gql_mutation_update_paymentplan_perms):
            raise ValidationError(_("mutation.authentication_required"))

        if PaymentPlanService.check_unique_code(data['code'], data['id']):
            raise ValidationError(_("mutation.payment_plan_code_duplicated"))

    @classmethod
    def _mutate(cls, user, **data):
        if "date_valid_to" not in data:
            data['date_valid_to'] = None
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')
        # looked up among the rows the user may read (core row security), never the
        # whole table; a row out of reach does not exist for them
        updated_object = cls._target_queryset(user).filter(id=data['id']).first()
        if updated_object is None:
            cls._object_not_exist_exception(obj_uuid=data['id'])
        content_type = ContentType.objects.get(model=data['benefit_plan_type'].lower())
        data['benefit_plan_type'] = content_type
        [setattr(updated_object, key, data[key]) for key in data]
        cls.update_object(user=user, object_to_update=updated_object)

    class Input(PaymentPlanUpdateInputType):
        pass


class DeletePaymentPlanMutation(BaseHistoryModelDeleteMutationMixin, BaseDeleteMutation):
    _mutation_class = "PaymentPlanMutation"
    _mutation_module = "contribution_plan"
    _model = PaymentPlan

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                ContributionPlanConfig.gql_mutation_delete_paymentplan_perms):
            raise ValidationError(_("mutation.authentication_required"))

    class Input(DeleteInputType):
        pass


class ReplacePaymentPlanMutation(BaseHistoryModelReplaceMutationMixin, BaseReplaceMutation):
    _mutation_class = "PaymentPlanMutation"
    _mutation_module = "contribution_plan"
    _model = PaymentPlan

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                ContributionPlanConfig.gql_mutation_replace_paymentplan_perms):
            raise ValidationError(_("mutation.authentication_required"))

    class Input(PaymentPlanReplaceInputType):
        pass
