import base64
import pickle
from typing import Union

from django.db.models import QuerySet

from django_glue.access.access import Access
from django_glue.glue.glue import BaseModelGlue, GlueActionResult
from django_glue.glue.model_object.fields.tools import \
    model_object_fields_glue_from_model
from django_glue.glue.model_object.glue import ModelGlueFieldConfig
from django_glue.glue.post_data import BaseActionKwargs
from django_glue.glue.query_set.actions import QuerySetGlueAction
from django_glue.glue.query_set.session_data import QuerySetGlueSessionData
from django_glue.session import Session


class QuerySetGlue(BaseModelGlue):
    def __init__(
            self,
            unique_name: str,
            session: Session,
            field_config: ModelGlueFieldConfig,
            query_set: QuerySet,
            access: Union[Access, str] = Access.VIEW,
    ):
        super().__init__(
            unique_name=unique_name,
            session=session,
            field_config=field_config,
            model_class=query_set.model,
            access=access
        )

        self.query_set = query_set

    def _encode_query_set(self) -> str:
        return base64.b64encode(pickle.dumps(self.query_set.query)).decode()

    def to_session_data(self) -> QuerySetGlueSessionData:
        return QuerySetGlueSessionData(
            unique_name=self.unique_name,
            query_set_str=self._encode_query_set(),
            glue_type=self.glue_type,
            fields=model_object_fields_glue_from_model(self.model, self.included_fields, self.excluded_fields).to_dict(),
            access=self.access,
            included_fields=self.included_fields,
            excluded_fields=self.excluded_fields,
            included_methods=self.included_methods,
        )

    def process_action(
        self,
        action: QuerySetGlueAction,
        action_kwargs: BaseActionKwargs | None = None,
    ) -> GlueActionResult:
        match action:
            case QuerySetGlueAction.ALL:
                self.all()
            case QuerySetGlueAction.GET:
                self.get()
            case QuerySetGlueAction.FILTER:
                self.filter(action_kwargs)
            case QuerySetGlueAction.DELETE:
                self.delete()
            case QuerySetGlueAction.METHOD:
                self.method(action_kwargs)

        return GlueActionResult(success=True, message=message, data=)