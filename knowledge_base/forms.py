from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from .models import ActUser, Post


# ─────────────────────────────────────────────────────
# REGISTRATION FORM
# ─────────────────────────────────────────────────────
class EmployeeRegistrationForm(UserCreationForm):

    email = forms.EmailField(
        label='ACT Corporate Email',
        help_text='You must use your @actcorp.in email address.',
        widget=forms.EmailInput(attrs={
            'placeholder': 'yourname@actcorp.in',
            'autocomplete': 'email',
        })
    )
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'First name'})
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'Last name'})
    )
    department = forms.CharField(
        max_length=100,
        required=False,
        help_text='e.g. Network Operations, Customer Experience',
        widget=forms.TextInput(attrs={'placeholder': 'Your department (optional)'})
    )

    class Meta:
        model = ActUser
        fields = ('email', 'first_name', 'last_name', 'department')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if not email.endswith('@actcorp.in'):
            raise ValidationError(
                'Registration is only open to @actcorp.in email addresses.'
            )
        if ActUser.objects.filter(email=email).exists():
            raise ValidationError(
                'An account with this email already exists.'
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name  = self.cleaned_data['first_name']
        user.last_name   = self.cleaned_data['last_name']
        user.department  = self.cleaned_data.get('department', '')
        user.role        = ActUser.Role.EMPLOYEE
        if commit:
            user.save()
        return user


# ─────────────────────────────────────────────────────
# LOGIN FORM
# ─────────────────────────────────────────────────────
class ActLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='ACT Corporate Email',
        widget=forms.EmailInput(attrs={
            'placeholder': 'yourname@actcorp.in',
            'autocomplete': 'email',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Your password',
            'autocomplete': 'current-password',
        })
    )


# ─────────────────────────────────────────────────────
# PROFILE EDIT FORM
# ─────────────────────────────────────────────────────
class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = ActUser
        fields = ('first_name', 'last_name', 'department', 'bio', 'avatar')
        widgets = {
            'bio': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'A short bio visible on your author profile...'
            }),
            'department': forms.TextInput(attrs={
                'placeholder': 'e.g. Network Operations'
            }),
        }


# ─────────────────────────────────────────────────────
# POST CREATION FORM (Updated with Multimedia)
# ─────────────────────────────────────────────────────
class PostForm(forms.ModelForm):
    class Meta:
        model   = Post
        fields = [
            'title',
            'category',
            'tags',
            'body',
            # ── new fields ──
            'image_file',
            'audio_file',
            'video_file',
            'pdf_file',
            'ppt_file',
            'doc_file',
            'external_url',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Post title...'
            }),
            'body': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 10
            }),
            'external_url': forms.URLInput(attrs={
                'class': 'form-input',
                'placeholder': 'https://...'
            }),
        }