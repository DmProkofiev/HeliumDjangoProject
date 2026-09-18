from django import forms

class MessageForm(forms.Form):
    text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Введите сообщение...',
            'class': 'message-input',
        }),
        label='',
        max_length=2000,
    )