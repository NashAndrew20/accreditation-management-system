from django import forms


class CommunicationMessageForm(forms.Form):
    body = forms.CharField(
        max_length=2000,
        strip=True,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Type a message...',
                'autocomplete': 'off',
                'maxlength': '2000',
                'required': True,
            },
        ),
    )
