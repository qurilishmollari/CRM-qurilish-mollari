from .models import Document


def allowed_document_kinds(user):
    if user.has_perm('crm.manage_inventory_documents'):
        return Document.Kind.values
    return [Document.Kind.SALE, Document.Kind.RETURN]


def visible_documents(user):
    return Document.objects.filter(kind__in=allowed_document_kinds(user))
