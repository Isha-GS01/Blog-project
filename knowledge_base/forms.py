from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import ActUser, Post


# ─────────────────────────────────────────────────────
# REGISTRATION — STEP 1: Email submission
# ─────────────────────────────────────────────────────
class RegistrationEmailForm(forms.Form):
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'autocomplete': 'email',
            'class': 'form-control',
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if ActUser.objects.filter(email=email).exists():
            raise ValidationError(
                'An account with this email already exists. '
                'Please sign in instead.'
            )
        return email


# ─────────────────────────────────────────────────────
# REGISTRATION — STEP 2: OTP verification
# ─────────────────────────────────────────────────────
class OTPVerificationForm(forms.Form):
    otp_code = forms.CharField(
        label='One-Time Password',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': '6-digit code',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
            'class': 'form-control otp-input',
        })
    )

    def clean_otp_code(self):
        code = self.cleaned_data.get('otp_code', '').strip()
        if not code.isdigit():
            raise ValidationError('OTP must contain digits only.')
        return code


# ─────────────────────────────────────────────────────
# REGISTRATION — STEP 3: Password + Profile details
# ─────────────────────────────────────────────────────
class RegistrationProfileForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'First name', 'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'Last name', 'class': 'form-control'})
    )
    department = forms.CharField(
        max_length=100,
        required=False,
        help_text='e.g. Network Operations, Customer Experience',
        widget=forms.TextInput(attrs={'placeholder': 'Your department (optional)', 'class': 'form-control'})
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Create a strong password',
            'autocomplete': 'new-password',
            'class': 'form-control',
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Repeat your password',
            'autocomplete': 'new-password',
            'class': 'form-control',
        })
    )

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'The two passwords do not match.')
        return cleaned


# ─────────────────────────────────────────────────────
# LOGIN FORM
# ─────────────────────────────────────────────────────
class ActLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email',
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
# POST CREATION / EDIT FORM  ← only this class changed
# ─────────────────────────────────────────────────────
class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = [
            'title',
            'category',
            'tags',
            'body',
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
                'class': 'pf-input pf-input--title',
                'placeholder': 'Give your post a clear title...',
            }),
            # Hidden — Quill syncs its HTML into this field on submit
            'body': forms.HiddenInput(attrs={
                'id': 'id_body',
            }),
            'external_url': forms.URLInput(attrs={
                'class': 'pf-input',
                'placeholder': 'https://drive.google.com/… or YouTube link, etc.',
            }),
        }

    def clean_body(self):
        """Reject submissions where Quill left an empty editor."""
        body = self.cleaned_data.get('body', '').strip()
        if body in ('', '<p><br></p>'):
            raise ValidationError('Content is required.')
        return body