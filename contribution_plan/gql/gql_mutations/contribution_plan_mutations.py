
from django.contrib.contenttypes.models import ContentType


from contribution_plan.apps import ContributionPlanConfig
from core.gql.gql_mutations import DeleteInputType
from contribution_plan.services import ContributionPlanService
from core.gql.gql_mutations.base_mutation import BaseMutation, BaseDeleteMutation, BaseReplaceMutation, \
    BaseHistoryModelCreateMutationMixin, BaseHistoryModelUpdateMutationMixin, \
    BaseHistoryModelDeleteMutationMixin, BaseHistoryModelReplaceMutationMixin
from contribution_plan.gql.gql_mutations import ContributionPlanInputType, ContributionPlanUpdateInputType, \
    ContributionPlanReplaceInputType
from contribution_plan.models import ContributionPlan
from django.utils.translation import gettext as _
from django.core.exceptions import PermissionDenied, ValidationError


class CreateContributionPlanMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "ContributionPlanMutation"
    _mutation_module = "contribution_plan"
    _model = ContributionPlan

    class Input(ContributionPlanInputType):
        pass

    @classmethod
    def create_object(cls, user, object_data):
        content_type = ContentType.objects.get(model=object_data['benefit_plan_type'].lower())
        object_data['benefit_plan_type'] = content_type
        obj = cls._model(**object_data)
        obj.save(username=user.username)
        return obj

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(ContributionPlanConfig.gql_mutation_create_contributionplan_perms):
            raise PermissionDenied(_("unauthorized"))
        if ContributionPlanService.check_unique_code(data['code']):
            raise ValidationError(_("mutation.cp_code_duplicated"))


class UpdateContributionPlanMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "ContributionPlanMutation"
    _mutation_module = "contribution_plan"
    _model = ContributionPlan

    class Input(ContributionPlanUpdateInputType):
        pass

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(ContributionPlanConfig.gql_mutation_update_contributionplan_perms):
            raise PermissionDenied(_("unauthorized"))


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


class DeleteContributionPlanMutation(BaseHistoryModelDeleteMutationMixin, BaseDeleteMutation):
    _mutation_class = "ContributionPlanMutation"
    _mutation_module = "contribution_plan"
    _model = ContributionPlan

    class Input(DeleteInputType):
        pass

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(ContributionPlanConfig.gql_mutation_delete_contributionplan_perms):
            raise PermissionDenied(_("unauthorized"))


class ReplaceContributionPlanMutation(BaseHistoryModelReplaceMutationMixin, BaseReplaceMutation):
    _mutation_class = "ContributionPlanMutation"
    _mutation_module = "contribution_plan"
    _model = ContributionPlan

    class Input(ContributionPlanReplaceInputType):
        pass

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(ContributionPlanConfig.gql_mutation_replace_contributionplan_perms):
            raise PermissionDenied(_("unauthorized"))
