from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import (
    UserProfile, TaskDetail, UserComment,
    Category, KnowledgeBase,
    Department, DepartmentMember, CannedResponse,
    TaskRating,
)

class LoginForm(forms.Form):
    LOGIN_AS_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
    ]

    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your username",
            "autofocus": True,
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your password",
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Remember me",
    )
    login_as = forms.ChoiceField(
        choices=LOGIN_AS_CHOICES,
        initial='user',
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Login As",
    )


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        label="First Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First Name"}),
        help_text="Enter your first name",
    )
    last_name = forms.CharField(
        label="Last Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last Name"}),
        help_text="Enter your last name",
    )
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Choose a username"}),
        help_text="Letters, digits and @/./+/-/_ only",
    )
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "your.email@example.com"}),
        help_text="We'll never share your email",
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Create a password"}),
        help_text="At least 8 characters",
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirm your password"}),
        help_text="Enter the same password again",
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email


class UserProfileForm(forms.ModelForm):
    Address = forms.CharField(
        label="Address",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Street Address"}),
        required=False,
    )
    City = forms.CharField(
        label="City",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "City"}),
        required=False,
    )
    State = forms.CharField(
        label="State",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "State"}),
        required=False,
    )
    Profile_Image = forms.ImageField(
        label="Profile Image",
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".png,.jpg,.jpeg"}),
    )
    phone = forms.CharField(
        label="Phone Number",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+1 (555) 123-4567"}),
    )

    class Meta:
        model = UserProfile
        fields = ('Address', 'City', 'State', 'Profile_Image', 'phone', 'email_notifications')
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_Profile_Image(self):
        image = self.cleaned_data.get('Profile_Image')
        if not image:
            return image

        name = (image.name or '').lower()
        allowed_ext = ('.png', '.jpg', '.jpeg')
        if not name.endswith(allowed_ext):
            raise ValidationError("Only PNG and JPEG images are allowed.")

        content_type = getattr(image, 'content_type', '')
        allowed_types = ('image/png', 'image/jpeg')
        if content_type and content_type not in allowed_types:
            raise ValidationError("Only PNG and JPEG images are allowed.")

        return image


class AccountSettingsForm(forms.Form):
    ACTION_CHOICES = [
        ('department',    'Update Department'),
        ('toggle_status', 'Toggle Account Status'),
    ]

    target_user = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('username'),
        label="Select User",
        empty_label="- Choose a user -",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        label="Action",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        label="Department",
        empty_label="- Select department -",
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class DepartmentMemberForm(forms.Form):
    ROLE_CHOICES = [
        ('MEMBER', 'Member'),
        ('LEAD', 'Lead'),
        ('MANAGER', 'Manager'),
        ('HEAD', 'Head'),
    ]

    user_id = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        label="Select User",
        empty_label="- Choose a user -",
        widget=forms.Select(attrs={"class": "form-select"}),
        to_field_name='id',
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        initial='MEMBER',
        label="Department Role",
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class TaskDetailForm(forms.ModelForm):
    TASK_TITLE = forms.CharField(
        label="Task Title",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Brief summary of the task",
        }),
        help_text="Keep it concise and descriptive",
    )
    TASK_DUE_DATE = forms.DateField(
        label='Task Due Date',
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        help_text="When should this be completed?",
    )
    TASK_DESCRIPTION = forms.CharField(
        label="Task Description",
        widget=forms.Textarea(attrs={
            "class": "form-control", "rows": "5",
            "placeholder": "Describe the task in detail...",
        }),
        help_text="Provide as much detail as possible",
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label="Select Category",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Category",
    )
    priority = forms.ChoiceField(
        choices=[('', 'Select Priority')] + TaskDetail.PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Priority",
    )
    assigned_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        empty_label="- Select department -",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Assign to Department",
        help_text="Select the department to handle this ticket",
    )

    class Meta:
        model = TaskDetail
        fields = [
            'TASK_TITLE', 'TASK_DESCRIPTION', 'category', 'priority',
            'assigned_department', 'TASK_DUE_DATE',
        ]

    def clean_TASK_TITLE(self):
        title = self.cleaned_data.get('TASK_TITLE')
        if len(title) < 10:
            raise ValidationError("Title must be at least 10 characters.")
        return title

    def clean_TASK_DESCRIPTION(self):
        desc = self.cleaned_data.get('TASK_DESCRIPTION')
        if len(desc) < 20:
            raise ValidationError("Please provide more detail (at least 20 characters).")
        return desc


class TaskUpdateForm(forms.ModelForm):
    TASK_TITLE = forms.CharField(
        label="Task Title",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    TASK_DESCRIPTION = forms.CharField(
        label="Task Description",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": "5"}),
    )
    TASK_DUE_DATE = forms.DateField(
        label='Due Date',
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    TASK_STATUS = forms.ChoiceField(
        choices=TaskDetail.choice,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Status",
    )
    priority = forms.ChoiceField(
        choices=TaskDetail.PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Priority",
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Category",
    )
    assigned_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        empty_label="Not Assigned",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Assigned Department",
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        required=False,
        empty_label="- Leave unassigned -",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Assign To",
    )

    class Meta:
        model = TaskDetail
        fields = (
            'TASK_TITLE', 'TASK_DESCRIPTION', 'TASK_DUE_DATE',
            'TASK_STATUS', 'priority', 'category',
            'assigned_department', 'assigned_to',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance and instance.assigned_department:
            dept_user_ids = DepartmentMember.objects.filter(
                department=instance.assigned_department,
                is_active=True,
            ).values_list('user_id', flat=True)
            self.fields['assigned_to'].queryset = User.objects.filter(
                id__in=dept_user_ids, is_active=True
            ).order_by('username')
            self.fields['assigned_to'].help_text = (
                f"Members of {instance.assigned_department.name}"
            )


class TaskFilterForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search tickets...'}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + TaskDetail.choice,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    priority = forms.ChoiceField(
        required=False,
        choices=[('', 'All Priorities')] + TaskDetail.PRIORITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    category = forms.ModelChoiceField(
        required=False,
        queryset=Category.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="All Categories",
    )
    department = forms.ModelChoiceField(
        required=False,
        queryset=Department.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="All Departments",
        label="Department",
    )
    my_tasks = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Mine Only",
    )


class UserCommentForm(forms.ModelForm):
    class Meta:
        model = UserComment
        fields = ('Reopen_comment', 'Closing_comment', 'TextFile')
        widgets = {
            'Reopen_comment': forms.Textarea(attrs={
                'rows': 4, 'class': 'form-control',
                'placeholder': 'Explain why you are reopening this ticket...',
            }),
            'Closing_comment': forms.Textarea(attrs={
                'rows': 4, 'class': 'form-control',
                'placeholder': 'Describe how you resolved this ticket...',
            }),
            'TextFile': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt,.jpg,.jpeg,.png',
            }),
        }
        labels = {
            'Reopen_comment': 'Reopening Remarks',
            'Closing_comment': 'Closing Remarks',
            'TextFile': 'Attach File (Optional)',
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'description', 'icon', 'color', 'is_active', 'ml_keywords')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'fa-folder'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ml_keywords': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'keyword1, keyword2, keyword3',
            }),
        }


class KnowledgeBaseForm(forms.ModelForm):
    class Meta:
        model = KnowledgeBase
        fields = ('title', 'content', 'category', 'keywords', 'is_published')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Article Title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'keywords': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': 'keyword1, keyword2, keyword3',
            }),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CannedResponseForm(forms.ModelForm):
    class Meta:
        model = CannedResponse
        fields = ['title', 'content', 'category', 'department', 'is_public', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 6,
                'placeholder': 'Use {{task_id}}, {{user_name}}, {{task_title}}',
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'content': 'Variables: {{task_id}}, {{user_name}}, {{task_title}}, {{assigned_to}}',
            'is_public': 'If unchecked, only you can use this response',
        }


class CannedResponseSelectForm(forms.Form):
    canned_response = forms.ModelChoiceField(
        queryset=CannedResponse.objects.filter(is_active=True),
        required=False,
        empty_label="Select a canned response...",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'cannedResponseSelect'}),
    )


class TaskRatingForm(forms.ModelForm):
    class Meta:
        model = TaskRating
        fields = ['rating', 'resolution_quality', 'response_time_rating',
                  'agent_helpfulness', 'feedback']
        widgets = {
            'rating': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'resolution_quality': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'response_time_rating': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'agent_helpfulness': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Share your experience (optional)...',
            }),
        }
        labels = {
            'rating': 'Overall Satisfaction',
            'resolution_quality': 'How well was your issue resolved?',
            'response_time_rating': 'How satisfied are you with the response time?',
            'agent_helpfulness': 'How helpful was the resolver?',
            'feedback': 'Additional Comments',
        }


def get_available_canned_responses(user, category=None, department=None):
    from django.db.models import Q
    qs = CannedResponse.objects.filter(is_active=True).filter(
        Q(is_public=True) | Q(created_by=user)
    )
    if category:
        qs = qs.filter(Q(category=category) | Q(category__isnull=True))
    if department:
        qs = qs.filter(Q(department=department) | Q(department__isnull=True))
    return qs.order_by('-usage_count', 'title')
