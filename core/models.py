from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse

class Tag(models.Model):
    name = models.CharField('название', max_length=50, unique=True)
    slug = models.SlugField('slug', max_length=60, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'тег'
        verbose_name_plural = 'теги'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Category(models.Model):
    name = models.CharField('название', max_length=80, unique=True)
    slug = models.SlugField('slug', max_length=90, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Publication(models.Model):
    # Тип публикации: услуга (исполнитель предлагает) или заказ (заказчик ищет)
    TYPE_CHOICES = (
        ('service', 'Услуга'),
        ('order', 'Заказ'),
    )

    STATUS_CHOICES = (
        ('active', 'Активна'),
        ('in_progress', 'В работе'),
        ('closed', 'Закрыта'),
        ('archived', 'Архивирована'),
    )

    PRICE_TYPE_CHOICES = (
        ('fixed', 'Фиксированная'),
        ('hourly', 'Почасовая'),
        ('negotiable', 'Договорная'),
    )

    # Тип и статус
    publication_type = models.CharField(
        'Тип публикации',
        max_length=10,
        choices=TYPE_CHOICES,
        default='service',
    )
    status = models.CharField(
        'Статус',
        max_length=15,
        choices=STATUS_CHOICES,
        default='active',
    )

    # Связи
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='publications',
        verbose_name='Автор',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='publications',
        verbose_name='Категория',
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='publications',
        verbose_name='Теги',
    )

    # Основные поля
    title = models.CharField('Заголовок', max_length=200)
    slug = models.SlugField('Слаг', max_length=220, unique=True, blank=True)
    description = models.TextField('Описание')
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, null=True, blank=True)
    price_type = models.CharField(
        'Тип цены',
        max_length=10,
        choices=PRICE_TYPE_CHOICES,
        default='fixed',
    )
    deadline = models.DateField('Срок выполнения', null=True, blank=True)
    image = models.ImageField('Изображение', upload_to='publications/', blank=True, null=True)

    # Метаданные
    views = models.PositiveIntegerField('Просмотры', default=0)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'публикация'
        verbose_name_plural = 'публикации'
        indexes = [
            models.Index(fields=['publication_type', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'[{self.get_publication_type_display()}] {self.title}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Publication.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Ссылка на страницу публикации."""
        return reverse('core:publication_detail', kwargs={'slug': self.slug})

    def get_price_display(self):
        """Форматированный вывод цены с учётом типа."""
        if self.price is None:
            return 'Цена не указана'
        price_str = f'{self.price:.2f} ₽'
        if self.price_type == 'hourly':
            return f'{price_str} / час'
        if self.price_type == 'negotiable':
            return 'Договорная'
        return price_str