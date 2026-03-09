from django import forms
from datetime import date, timedelta
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import (
    UserProfile, TicketDetail, UserComment,
    Category, KnowledgeBase,
    Department, DepartmentMember, CannedResponse,
    TicketRating,
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
    COUNTRY_CODE_CHOICES = [
        ('+93', 'Afghanistan (+93)'),
        ('+355', 'Albania (+355)'),
        ('+213', 'Algeria (+213)'),
        ('+376', 'Andorra (+376)'),
        ('+244', 'Angola (+244)'),
        ('+1', 'Antigua and Barbuda (+1)'),
        ('+54', 'Argentina (+54)'),
        ('+374', 'Armenia (+374)'),
        ('+61', 'Australia (+61)'),
        ('+43', 'Austria (+43)'),
        ('+994', 'Azerbaijan (+994)'),
        ('+1', 'Bahamas (+1)'),
        ('+973', 'Bahrain (+973)'),
        ('+880', 'Bangladesh (+880)'),
        ('+1', 'Barbados (+1)'),
        ('+375', 'Belarus (+375)'),
        ('+32', 'Belgium (+32)'),
        ('+501', 'Belize (+501)'),
        ('+229', 'Benin (+229)'),
        ('+975', 'Bhutan (+975)'),
        ('+591', 'Bolivia (+591)'),
        ('+387', 'Bosnia and Herzegovina (+387)'),
        ('+267', 'Botswana (+267)'),
        ('+55', 'Brazil (+55)'),
        ('+673', 'Brunei (+673)'),
        ('+359', 'Bulgaria (+359)'),
        ('+226', 'Burkina Faso (+226)'),
        ('+257', 'Burundi (+257)'),
        ('+855', 'Cambodia (+855)'),
        ('+237', 'Cameroon (+237)'),
        ('+1', 'Canada (+1)'),
        ('+238', 'Cape Verde (+238)'),
        ('+236', 'Central African Republic (+236)'),
        ('+235', 'Chad (+235)'),
        ('+56', 'Chile (+56)'),
        ('+86', 'China (+86)'),
        ('+57', 'Colombia (+57)'),
        ('+269', 'Comoros (+269)'),
        ('+242', 'Congo (+242)'),
        ('+243', 'Congo, DR (+243)'),
        ('+506', 'Costa Rica (+506)'),
        ('+385', 'Croatia (+385)'),
        ('+53', 'Cuba (+53)'),
        ('+357', 'Cyprus (+357)'),
        ('+420', 'Czech Republic (+420)'),
        ('+45', 'Denmark (+45)'),
        ('+253', 'Djibouti (+253)'),
        ('+1', 'Dominica (+1)'),
        ('+1', 'Dominican Republic (+1)'),
        ('+593', 'Ecuador (+593)'),
        ('+20', 'Egypt (+20)'),
        ('+503', 'El Salvador (+503)'),
        ('+240', 'Equatorial Guinea (+240)'),
        ('+291', 'Eritrea (+291)'),
        ('+372', 'Estonia (+372)'),
        ('+251', 'Ethiopia (+251)'),
        ('+679', 'Fiji (+679)'),
        ('+358', 'Finland (+358)'),
        ('+33', 'France (+33)'),
        ('+241', 'Gabon (+241)'),
        ('+220', 'Gambia (+220)'),
        ('+995', 'Georgia (+995)'),
        ('+49', 'Germany (+49)'),
        ('+233', 'Ghana (+233)'),
        ('+30', 'Greece (+30)'),
        ('+1', 'Grenada (+1)'),
        ('+502', 'Guatemala (+502)'),
        ('+224', 'Guinea (+224)'),
        ('+245', 'Guinea-Bissau (+245)'),
        ('+592', 'Guyana (+592)'),
        ('+509', 'Haiti (+509)'),
        ('+504', 'Honduras (+504)'),
        ('+36', 'Hungary (+36)'),
        ('+354', 'Iceland (+354)'),
        ('+91', 'India (+91)'),
        ('+62', 'Indonesia (+62)'),
        ('+98', 'Iran (+98)'),
        ('+964', 'Iraq (+964)'),
        ('+353', 'Ireland (+353)'),
        ('+972', 'Israel (+972)'),
        ('+39', 'Italy (+39)'),
        ('+225', "Cote d'Ivoire (+225)"),
        ('+1', 'Jamaica (+1)'),
        ('+81', 'Japan (+81)'),
        ('+962', 'Jordan (+962)'),
        ('+7', 'Kazakhstan (+7)'),
        ('+254', 'Kenya (+254)'),
        ('+686', 'Kiribati (+686)'),
        ('+383', 'Kosovo (+383)'),
        ('+965', 'Kuwait (+965)'),
        ('+996', 'Kyrgyzstan (+996)'),
        ('+856', 'Laos (+856)'),
        ('+371', 'Latvia (+371)'),
        ('+961', 'Lebanon (+961)'),
        ('+266', 'Lesotho (+266)'),
        ('+231', 'Liberia (+231)'),
        ('+218', 'Libya (+218)'),
        ('+423', 'Liechtenstein (+423)'),
        ('+370', 'Lithuania (+370)'),
        ('+352', 'Luxembourg (+352)'),
        ('+389', 'North Macedonia (+389)'),
        ('+261', 'Madagascar (+261)'),
        ('+265', 'Malawi (+265)'),
        ('+60', 'Malaysia (+60)'),
        ('+960', 'Maldives (+960)'),
        ('+223', 'Mali (+223)'),
        ('+356', 'Malta (+356)'),
        ('+692', 'Marshall Islands (+692)'),
        ('+222', 'Mauritania (+222)'),
        ('+230', 'Mauritius (+230)'),
        ('+52', 'Mexico (+52)'),
        ('+691', 'Micronesia (+691)'),
        ('+373', 'Moldova (+373)'),
        ('+377', 'Monaco (+377)'),
        ('+976', 'Mongolia (+976)'),
        ('+382', 'Montenegro (+382)'),
        ('+212', 'Morocco (+212)'),
        ('+258', 'Mozambique (+258)'),
        ('+95', 'Myanmar (+95)'),
        ('+264', 'Namibia (+264)'),
        ('+674', 'Nauru (+674)'),
        ('+977', 'Nepal (+977)'),
        ('+31', 'Netherlands (+31)'),
        ('+64', 'New Zealand (+64)'),
        ('+505', 'Nicaragua (+505)'),
        ('+227', 'Niger (+227)'),
        ('+234', 'Nigeria (+234)'),
        ('+850', 'North Korea (+850)'),
        ('+47', 'Norway (+47)'),
        ('+968', 'Oman (+968)'),
        ('+92', 'Pakistan (+92)'),
        ('+680', 'Palau (+680)'),
        ('+970', 'Palestine (+970)'),
        ('+507', 'Panama (+507)'),
        ('+675', 'Papua New Guinea (+675)'),
        ('+595', 'Paraguay (+595)'),
        ('+51', 'Peru (+51)'),
        ('+63', 'Philippines (+63)'),
        ('+48', 'Poland (+48)'),
        ('+351', 'Portugal (+351)'),
        ('+974', 'Qatar (+974)'),
        ('+40', 'Romania (+40)'),
        ('+7', 'Russia (+7)'),
        ('+250', 'Rwanda (+250)'),
        ('+1', 'Saint Kitts and Nevis (+1)'),
        ('+1', 'Saint Lucia (+1)'),
        ('+1', 'Saint Vincent and the Grenadines (+1)'),
        ('+685', 'Samoa (+685)'),
        ('+378', 'San Marino (+378)'),
        ('+239', 'Sao Tome and Principe (+239)'),
        ('+966', 'Saudi Arabia (+966)'),
        ('+221', 'Senegal (+221)'),
        ('+381', 'Serbia (+381)'),
        ('+248', 'Seychelles (+248)'),
        ('+232', 'Sierra Leone (+232)'),
        ('+65', 'Singapore (+65)'),
        ('+421', 'Slovakia (+421)'),
        ('+386', 'Slovenia (+386)'),
        ('+677', 'Solomon Islands (+677)'),
        ('+252', 'Somalia (+252)'),
        ('+27', 'South Africa (+27)'),
        ('+82', 'South Korea (+82)'),
        ('+211', 'South Sudan (+211)'),
        ('+34', 'Spain (+34)'),
        ('+94', 'Sri Lanka (+94)'),
        ('+249', 'Sudan (+249)'),
        ('+597', 'Suriname (+597)'),
        ('+46', 'Sweden (+46)'),
        ('+41', 'Switzerland (+41)'),
        ('+963', 'Syria (+963)'),
        ('+886', 'Taiwan (+886)'),
        ('+992', 'Tajikistan (+992)'),
        ('+255', 'Tanzania (+255)'),
        ('+66', 'Thailand (+66)'),
        ('+670', 'Timor-Leste (+670)'),
        ('+228', 'Togo (+228)'),
        ('+676', 'Tonga (+676)'),
        ('+1', 'Trinidad and Tobago (+1)'),
        ('+216', 'Tunisia (+216)'),
        ('+90', 'Turkey (+90)'),
        ('+993', 'Turkmenistan (+993)'),
        ('+688', 'Tuvalu (+688)'),
        ('+256', 'Uganda (+256)'),
        ('+380', 'Ukraine (+380)'),
        ('+971', 'United Arab Emirates (+971)'),
        ('+44', 'United Kingdom (+44)'),
        ('+1', 'United States (+1)'),
        ('+598', 'Uruguay (+598)'),
        ('+998', 'Uzbekistan (+998)'),
        ('+678', 'Vanuatu (+678)'),
        ('+379', 'Vatican City (+379)'),
        ('+58', 'Venezuela (+58)'),
        ('+84', 'Vietnam (+84)'),
        ('+967', 'Yemen (+967)'),
        ('+260', 'Zambia (+260)'),
        ('+263', 'Zimbabwe (+263)'),
        ('+1', 'Puerto Rico (+1)'),
        ('+1', 'Guam (+1)'),
        ('+1', 'US Virgin Islands (+1)'),
        ('+1', 'Northern Mariana Islands (+1)'),
        ('+297', 'Aruba (+297)'),
        ('+599', 'Curacao (+599)'),
        ('+590', 'Guadeloupe (+590)'),
        ('+596', 'Martinique (+596)'),
        ('+594', 'French Guiana (+594)'),
        ('+262', 'Reunion (+262)'),
        ('+268', 'Eswatini (+268)'),
        ('+290', 'Saint Helena (+290)'),
    ]

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
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "9876543210"}),
    )
    country_code = forms.ChoiceField(
        label="Country Code",
        required=False,
        choices=COUNTRY_CODE_CHOICES,
        initial='+91',
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = UserProfile
        fields = ('Address', 'City', 'State', 'Profile_Image', 'phone', 'email_notifications')
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.require_phone = kwargs.pop('require_phone', False)
        super().__init__(*args, **kwargs)
        if self.require_phone:
            self.fields['phone'].required = True
            self.fields['country_code'].required = True

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

    def clean_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip()
        if not phone:
            if self.require_phone:
                raise ValidationError("Phone number is required.")
            return ''

        digits = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits) < 6 or len(digits) > 12:
            raise ValidationError("Enter a valid phone number.")
        return digits

    def clean(self):
        cleaned_data = super().clean()
        phone = cleaned_data.get('phone') or ''
        country_code = cleaned_data.get('country_code') or ''

        if self.require_phone and phone and not country_code:
            self.add_error('country_code', "Please select a country code.")

        if phone and country_code:
            code_digits = ''.join(ch for ch in country_code if ch.isdigit())
            if len(code_digits + phone) > 15:
                self.add_error('phone', "Phone number is too long for the selected country code.")

        return cleaned_data

    def get_full_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip()
        if not phone:
            return ''
        country_code = (self.cleaned_data.get('country_code') or '').strip() or '+91'
        return f"{country_code}{phone}"


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


class TicketDetailForm(forms.ModelForm):
    TICKET_TITLE = forms.CharField(
        label="Ticket Title",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Brief summary of the ticket",
        }),
        help_text="Keep it concise and descriptive",
    )
    TICKET_DUE_DATE = forms.DateField(
        label='Ticket Due Date',
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        help_text="When should this be completed",
    )
    TICKET_DESCRIPTION = forms.CharField(
        label="Ticket Description",
        widget=forms.Textarea(attrs={
            "class": "form-control", "rows": "5",
            "placeholder": "Describe the ticket in detail...",
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
        choices=[('', 'Select Priority')] + TicketDetail.PRIORITY_CHOICES,
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
        model = TicketDetail
        fields = [
            'TICKET_TITLE', 'TICKET_DESCRIPTION', 'category', 'priority',
            'assigned_department', 'TICKET_DUE_DATE',
        ]

    def clean_TICKET_TITLE(self):
        title = self.cleaned_data.get('TICKET_TITLE')
        if len(title) < 10:
            raise ValidationError("Title must be at least 10 characters.")
        return title

    def clean_TICKET_DESCRIPTION(self):
        desc = self.cleaned_data.get('TICKET_DESCRIPTION')
        if len(desc) < 20:
            raise ValidationError("Please provide more detail (at least 20 characters).")
        return desc


class TicketCreateForm(forms.ModelForm):
    TICKET_TITLE = forms.CharField(
        label="Ticket Title",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Brief summary of the ticket",
        }),
        help_text="Keep it concise and descriptive",
    )
    TICKET_DUE_DATE = forms.DateField(
        label='Ticket Due Date',
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        help_text="When should this be completed",
    )
    TICKET_DESCRIPTION = forms.CharField(
        label="Ticket Description",
        widget=forms.Textarea(attrs={
            "class": "form-control", "rows": "5",
            "placeholder": "Describe the ticket in detail...",
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

    class Meta:
        model = TicketDetail
        fields = [
            'TICKET_TITLE', 'TICKET_DESCRIPTION', 'category', 'TICKET_DUE_DATE',
        ]

    def clean_TICKET_TITLE(self):
        title = self.cleaned_data.get('TICKET_TITLE')
        if len(title) < 10:
            raise ValidationError("Title must be at least 10 characters.")
        return title

    def clean_TICKET_DESCRIPTION(self):
        desc = self.cleaned_data.get('TICKET_DESCRIPTION')
        if len(desc) < 20:
            raise ValidationError("Please provide more detail (at least 20 characters).")
        return desc


class TicketUpdateForm(forms.ModelForm):
    TICKET_TITLE = forms.CharField(
        label="Ticket Title",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    TICKET_DESCRIPTION = forms.CharField(
        label="Ticket Description",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": "5"}),
    )
    TICKET_DUE_DATE = forms.DateField(
        label='Due Date',
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    TICKET_STATUS = forms.ChoiceField(
        choices=TicketDetail.choice,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Status",
    )
    priority = forms.ChoiceField(
        choices=TicketDetail.PRIORITY_CHOICES,
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
        model = TicketDetail
        fields = (
            'TICKET_TITLE', 'TICKET_DESCRIPTION', 'TICKET_DUE_DATE',
            'TICKET_STATUS', 'priority', 'category',
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


class AdminTicketRoutingForm(forms.ModelForm):
    priority = forms.ChoiceField(
        choices=TicketDetail.PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Priority",
    )
    assigned_department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        empty_label="Not Assigned",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Assigned Department",
    )
    extend_due_date = forms.DateField(
        required=False,
        label="Extend Due Date",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        help_text="Available only when the ticket is due or overdue.",
    )

    class Meta:
        model = TicketDetail
        fields = ('priority', 'assigned_department')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_extend_due_date = False
        if not self.instance or not self.instance.pk:
            self.fields.pop('extend_due_date', None)
            return

        if self.instance.TICKET_STATUS in ['Closed', 'Resolved']:
            self.fields.pop('extend_due_date', None)
            return

        # Admin can extend due date at any time for unresolved tickets.
        self.can_extend_due_date = True
        self.fields['extend_due_date'].help_text = (
            "Pick a date later than the current due date."
        )
        min_extend_date = self.instance.TICKET_DUE_DATE + timedelta(days=1)
        self.fields['extend_due_date'].widget.attrs['min'] = min_extend_date.isoformat()

    def clean_extend_due_date(self):
        new_due_date = self.cleaned_data.get('extend_due_date')
        if not new_due_date:
            return None

        if new_due_date <= self.instance.TICKET_DUE_DATE:
            raise ValidationError("Extended due date must be later than the current due date.")

        return new_due_date


class TicketFilterForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search tickets...'}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + TicketDetail.choice,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    priority = forms.ChoiceField(
        required=False,
        choices=[('', 'All Priorities')] + TicketDetail.PRIORITY_CHOICES,
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
    my_tickets = forms.BooleanField(
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
                'placeholder': 'Use {{ticket_id}}, {{user_name}}, {{ticket_title}}',
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'content': 'Variables: {{ticket_id}}, {{user_name}}, {{ticket_title}}, {{assigned_to}}',
            'is_public': 'If unchecked, only you can use this response',
        }


class CannedResponseSelectForm(forms.Form):
    canned_response = forms.ModelChoiceField(
        queryset=CannedResponse.objects.filter(is_active=True),
        required=False,
        empty_label="Select a canned response...",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'cannedResponseSelect'}),
    )


class TicketRatingForm(forms.ModelForm):
    class Meta:
        model = TicketRating
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
            'resolution_quality': 'How well was your issue resolved',
            'response_time_rating': 'How satisfied are you with the response time',
            'agent_helpfulness': 'How helpful was the resolver',
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


class UsernameEmailPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, username=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.requested_username = (username or "").strip()
        self._matched_users = []

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not self.requested_username:
            raise ValidationError("Invalid password reset request.")

        user_model = get_user_model()
        username_exists = user_model._default_manager.filter(
            username__iexact=self.requested_username,
            is_active=True,
        ).exists()
        if not username_exists:
            raise ValidationError("Username not found. Enter a valid registered username.")

        self._matched_users = list(
            user_model._default_manager.filter(
                username__iexact=self.requested_username,
                email__iexact=email,
                is_active=True,
            )
        )
        if not self._matched_users:
            raise ValidationError("Enter your own registered email for this username.")
        return email

    def get_users(self, email):
        return iter(self._matched_users)
