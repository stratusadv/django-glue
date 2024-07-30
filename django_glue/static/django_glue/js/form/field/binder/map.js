
let FORM_FIELD_TYPE_TO_GLUE_FORM_FIELD_MAP = {
    [DjangoModelFieldType.AUTO_FIELD]: GlueFormFieldBinder,
    [DjangoModelFieldType.BIG_AUTO_FIELD]: GlueFormFieldBinder,
    [DjangoModelFieldType.SMALL_AUTO_FIELD]: GlueFormFieldBinder,
    [DjangoModelFieldType.BOOLEAN]: GlueFormFieldBinder,
    [DjangoModelFieldType.CHAR]: GlueFormFieldBinder,
    [DjangoModelFieldType.DATE]: GlueFormFieldBinder,
    [DjangoModelFieldType.DATETIME]: GlueFormFieldBinder,
    [DjangoModelFieldType.DECIMAL]: GlueFormFieldBinder,
    [DjangoModelFieldType.DURATION]: GlueFormFieldBinder,
    [DjangoModelFieldType.EMAIL]: GlueFormFieldBinder,
    [DjangoModelFieldType.FILE]: GlueFormFieldBinder,
    [DjangoModelFieldType.FILE_PATH]: GlueFormFieldBinder,
    [DjangoModelFieldType.FLOAT]: GlueFormFieldBinder,
    [DjangoModelFieldType.FOREIGN_KEY]: GlueFormFieldBinder,
    [DjangoModelFieldType.ONE_TO_ONE]: GlueFormFieldBinder,
    [DjangoModelFieldType.MANY_TO_MANY]: GlueFormFieldBinder,
    [DjangoModelFieldType.INTEGER]: GlueFormFieldBinder,
    [DjangoModelFieldType.BIG_INTEGER]: GlueFormFieldBinder,
    [DjangoModelFieldType.SMALL_INTEGER]: GlueFormFieldBinder,
    [DjangoModelFieldType.GENERIC_IP_ADDRESS]: GlueFormFieldBinder,
    [DjangoModelFieldType.JSON]: GlueFormFieldBinder,
    [DjangoModelFieldType.POSITIVE_BIG_INTEGER]: GlueFormFieldBinder,
    [DjangoModelFieldType.POSITIVE_INTEGER]: GlueFormFieldBinder,
    [DjangoModelFieldType.POSITIVE_SMALL_INTEGER]: GlueFormFieldBinder,
    [DjangoModelFieldType.SLUG]: GlueFormFieldBinder,
    [DjangoModelFieldType.TEXT]: GlueFormFieldBinder,
    [DjangoModelFieldType.TIME]: GlueFormFieldBinder,
    [DjangoModelFieldType.URL]: GlueFormFieldBinder,
    [DjangoModelFieldType.UUID]: GlueFormFieldBinder
}

Object.freeze(FORM_FIELD_TYPE_TO_GLUE_FORM_FIELD_MAP);
