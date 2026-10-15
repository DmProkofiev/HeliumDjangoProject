from django import forms
from .models import Publication


class PublicationForm(forms.ModelForm):
    tags_input = forms.CharField(
        label='Теги',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Через запятую: дизайн, логотип, товар',
        }),
    )

    MAX_FILES = 10
    MAX_SIZE = 5 * 1024 * 1024
    ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

    class Meta:
        model = Publication
        fields = (
            'publication_type',
            'title',
            'description',
            'category',
            'price',
            'price_type',
            'deadline',
            'tags_input',
        )
        widgets = {
            'publication_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'price_type': forms.Select(attrs={'class': 'form-control'}),
            'deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            tags = self.instance.tags.values_list('name', flat=True)
            self.fields['tags_input'].initial = ', '.join(tags)

    def clean(self):
        cleaned = super().clean()
        raw = cleaned.get('tags_input', '') or ''
        names = [n.strip() for n in raw.split(',') if n.strip()]
        if len(names) > 30:
            raise forms.ValidationError('Слишком много тегов (макс. 30).')
        for n in names:
            if len(n) > 50:
                raise forms.ValidationError(f'Тег «{n}» длиннее 50 символов.')
        cleaned['tags_input'] = ', '.join(names)

        files = self.files.getlist('images_upload') if self.files else []
        if len(files) > self.MAX_FILES:
            raise forms.ValidationError(
                f'Максимум {self.MAX_FILES} изображений за раз.'
            )
        for f in files:
            if f.size > self.MAX_SIZE:
                raise forms.ValidationError(
                    f'Файл «{f.name}» больше {self.MAX_SIZE // (1024 * 1024)} МБ.'
                )
            ext = ('.' + f.name.rsplit('.', 1)[-1].lower()) if '.' in f.name else ''
            if ext not in self.ALLOWED_EXT:
                raise forms.ValidationError(f'Недопустимый формат файла: {f.name}')

        return cleaned