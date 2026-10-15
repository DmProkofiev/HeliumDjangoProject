from django.conf import settings
from django.core.files.storage import FileSystemStorage

publication_storage = FileSystemStorage(location=str(settings.PUBLICATION_STORAGE_ROOT), base_url=settings.PUBLICATION_STORAGE_URL)