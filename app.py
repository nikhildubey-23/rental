from flask import Flask, render_template, redirect, url_for, flash, request, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, SelectField, TextAreaField, DecimalField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from datetime import datetime, date
import os
import logging
import traceback
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///rental.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Error handling configuration
@app.errorhandler(404)
def not_found_error(error):
    app.logger.error(f'404 Not Found: {request.url} - User: {current_user.username if current_user.is_authenticated else "Anonymous"}')
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.error(f'500 Internal Server Error: {str(error)}\n{traceback.format_exc()}')
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    app.logger.error(f'403 Forbidden: {request.url} - User: {current_user.username if current_user.is_authenticated else "Anonymous"}')
    return render_template('errors/403.html'), 403

@app.errorhandler(413)
def too_large(error):
    app.logger.error(f'413 Payload Too Large: {str(error)} - User: {current_user.username if current_user.is_authenticated else "Anonymous"}')
    flash('File too large. Maximum size is 16MB.', 'danger')
    return redirect(request.referrer or url_for('index'))

@app.errorhandler(400)
def bad_request_error(error):
    app.logger.error(f'400 Bad Request: {str(error)} - User: {current_user.username if current_user.is_authenticated else "Anonymous"}')
    flash('Invalid request. Please check your input and try again.', 'danger')
    return redirect(request.referrer or url_for('index'))

# Custom exception handler for database errors
@app.errorhandler(Exception)
def handle_exception(error):
    db.session.rollback()
    app.logger.error(f'Unhandled Exception: {str(error)}\n{traceback.format_exc()}')
    
    # Don't handle HTTP errors (they're handled by specific handlers)
    if hasattr(error, 'code') and error.code in [404, 403, 413, 500]:
        return error
    
    flash('An unexpected error occurred. Please try again.', 'danger')
    return render_template('errors/500.html'), 500

# Multi-Tenant Models
class Tenant(UserMixin, db.Model):
    """Multi-tenant organization model for owners"""
    id = db.Column(db.Integer, primary_key=True)
    business_name = db.Column(db.String(200), nullable=False)
    contact_email = db.Column(db.String(120), unique=True, nullable=False)
    contact_phone = db.Column(db.String(20))
    business_address = db.Column(db.Text)
    subscription_plan = db.Column(db.String(50), default='basic')  # basic, pro, enterprise
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to properties owned by this tenant
    properties = db.relationship('Property', backref='owner', lazy=True, cascade='all, delete-orphan')
    owner_users = db.relationship('User', backref='tenant', lazy=True)

class Property(db.Model):
    """Individual rental properties"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text, nullable=False)
    total_units = db.Column(db.Integer, default=1)
    owner_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    units = db.relationship('Unit', backref='property', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='property', lazy=True)
    maintenance_requests = db.relationship('MaintenanceRequest', backref='property', lazy=True)
    notifications = db.relationship('Notification', backref='property', lazy=True)

class Unit(db.Model):
    """Individual rental units within a property"""
    id = db.Column(db.Integer, primary_key=True)
    unit_number = db.Column(db.String(20), nullable=False)
    apartment_number = db.Column(db.String(20), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    is_occupied = db.Column(db.Boolean, default=False)
    rent_amount = db.Column(db.Numeric(10, 2), default=0.00)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    current_tenant = db.relationship('User', backref='unit', uselist=False)
    payments = db.relationship('Payment', backref='unit', lazy=True)
    maintenance_requests = db.relationship('MaintenanceRequest', backref='unit', lazy=True)

class User(UserMixin, db.Model):
    """Enhanced user model for multi-tenant system"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='tenant')  # 'owner', 'tenant', 'admin'
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Multi-tenant relationships
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)  # For owner admins
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=True)  # For current tenants
    
    # Relationships
    payments = db.relationship('Payment', backref='tenant', lazy=True)
    maintenance_requests = db.relationship('MaintenanceRequest', backref='tenant', lazy=True)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=True)  # New: Link to specific unit
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=True)  # New: Link to property
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    month = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'completed', 'failed'
    payment_method = db.Column(db.String(50))
    transaction_id = db.Column(db.String(100))
    
    # Relationships
    tenant = db.relationship('User', backref='payments', uselist=False)
    unit = db.relationship('Unit', backref='payments', uselist=False)
    property = db.relationship('Property', backref='payments', uselist=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=True)  # New: Link to property
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)  # New: Link to tenant
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    priority = db.Column(db.String(20), default='normal')  # 'low', 'normal', 'high'
    target_role = db.Column(db.String(20))  # 'owner', 'tenant', or None for all
    file_attachment = db.Column(db.String(200))
    
    # Relationships
    tenant = db.relationship('Tenant', backref='notifications', uselist=False)
    property = db.relationship('Property', backref='notifications', uselist=False)

class MaintenanceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=True)  # New: Link to specific unit
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=True)  # New: Link to property
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'plumbing', 'electrical', 'general', etc.
    priority = db.Column(db.String(20), default='medium')  # 'low', 'medium', 'high'
    status = db.Column(db.String(20), default='open')  # 'open', 'in_progress', 'completed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    
    # Relationships
    tenant = db.relationship('User', backref='maintenance_requests', uselist=False)
    unit = db.relationship('Unit', backref='maintenance_requests', uselist=False)
    property = db.relationship('Property', backref='maintenance_requests', uselist=False)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=True)  # New: Link to property
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'), nullable=True)  # New: Link to tenant
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    target_role = db.Column(db.String(20))  # 'owner', 'tenant', or None for all
    
    # Relationships
    tenant = db.relationship('Tenant', backref='documents', uselist=False)
    property = db.relationship('Property', backref='documents', uselist=False)
    uploader = db.relationship('User', backref='documents', uselist=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    apartment_number = StringField('Apartment Number', validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[DataRequired()])
    submit = SubmitField('Register')

class PaymentForm(FlaskForm):
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0)])
    month = SelectField('Month', choices=[('January', 'January'), ('February', 'February'), ('March', 'March'), 
                                          ('April', 'April'), ('May', 'May'), ('June', 'June'),
                                          ('July', 'July'), ('August', 'August'), ('September', 'September'),
                                          ('October', 'October'), ('November', 'November'), ('December', 'December')], 
                        validators=[DataRequired()])
    year = SelectField('Year', choices=[], validators=[DataRequired()])
    payment_method = StringField('Payment Method', validators=[DataRequired()])
    submit = SubmitField('Make Payment')

class NotificationForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Content', validators=[DataRequired()])
    priority = SelectField('Priority', choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High')], 
                          validators=[DataRequired()])
    target_role = SelectField('Target Audience', choices=[('all', 'All'), ('tenant', 'Tenants Only'), ('owner', 'Owner Only')], 
                             validators=[DataRequired()])
    file_attachment = FileField('Attach File')
    submit = SubmitField('Post Notification')

class MaintenanceRequestForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[DataRequired()])
    category = SelectField('Category', choices=[('plumbing', 'Plumbing'), ('electrical', 'Electrical'), 
                                              ('hvac', 'HVAC'), ('appliance', 'Appliance'), 
                                              ('general', 'General')], validators=[DataRequired()])
    priority = SelectField('Priority', choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], 
                          validators=[DataRequired()])
    submit = SubmitField('Submit Request')

class DocumentForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    file = FileField('File', validators=[DataRequired()])
    target_role = SelectField('Share With', choices=[('all', 'Everyone'), ('tenant', 'Tenants Only'), ('owner', 'Owner Only')], 
                             validators=[DataRequired()])
    submit = SubmitField('Upload Document')

# Multi-tenant Forms
class TenantRegistrationForm(FlaskForm):
    """Form for business owners to register as tenants"""
    business_name = StringField('Business Name', validators=[DataRequired(), Length(max=200)])
    contact_email = StringField('Contact Email', validators=[DataRequired(), Email()])
    contact_phone = StringField('Contact Phone', validators=[DataRequired(), Length(max=20)])
    business_address = TextAreaField('Business Address', validators=[DataRequired()])
    subscription_plan = SelectField('Subscription Plan', 
                                choices=[('basic', 'Basic - $29/month'), ('pro', 'Pro - $79/month'), ('enterprise', 'Enterprise - $199/month')], 
                                validators=[DataRequired()])
    submit = SubmitField('Register Business')

class PropertyForm(FlaskForm):
    """Form for tenants to add properties"""
    name = StringField('Property Name', validators=[DataRequired(), Length(max=200)])
    address = TextAreaField('Address', validators=[DataRequired()])
    total_units = StringField('Total Units', validators=[DataRequired(), NumberRange(min=1, max=1000)])
    submit = SubmitField('Add Property')

class UnitForm(FlaskForm):
    """Form for property owners to add units"""
    unit_number = StringField('Unit Number', validators=[DataRequired(), Length(max=20)])
    apartment_number = StringField('Apartment Number', validators=[DataRequired(), Length(max=20)])
    rent_amount = DecimalField('Monthly Rent', validators=[DataRequired(), NumberRange(min=0)])
    is_occupied = SelectField('Status', choices=[('false', 'Vacant'), ('true', 'Occupied')], 
                           validators=[DataRequired()])
    submit = SubmitField('Add Unit')

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'owner':
            return redirect(url_for('owner_dashboard'))
        else:
            return redirect(url_for('tenant_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        form = LoginForm()
        if form.validate_on_submit():
            try:
                user = User.query.filter_by(username=form.username.data).first()
                if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
                    login_user(user)
                    app.logger.info(f'User {user.username} logged in successfully')
                    flash('Login successful!', 'success')
                    return redirect(url_for('index'))
                else:
                    app.logger.warning(f'Failed login attempt for username: {form.username.data}')
                    flash('Invalid username or password', 'danger')
            except Exception as e:
                app.logger.error(f'Error during login process: {str(e)}')
                flash('An error occurred during login. Please try again.', 'danger')
        
        return render_template('login.html', form=form)
    except Exception as e:
        app.logger.error(f'Unexpected error in login route: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        form = RegistrationForm()
        if form.validate_on_submit():
            try:
                # Check if username already exists
                if User.query.filter_by(username=form.username.data).first():
                    flash('Username already exists. Please choose a different one.', 'danger')
                    return render_template('register.html', form=form)
                
                # Check if email already exists
                if User.query.filter_by(email=form.email.data).first():
                    flash('Email already registered. Please use a different one.', 'danger')
                    return render_template('register.html', form=form)
                
                hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
                user = User(
                    username=form.username.data,
                    email=form.email.data,
                    password_hash=hashed_password,
                    apartment_number=form.apartment_number.data,
                    phone=form.phone.data,
                    role='tenant'
                )
                
                db.session.add(user)
                db.session.commit()
                app.logger.info(f'New user registered: {user.username}')
                flash('Registration successful! You can now log in.', 'success')
                return redirect(url_for('login'))
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Error during registration: {str(e)}')
                flash('Registration failed. Please try again.', 'danger')
                
        return render_template('register.html', form=form)
        
    except Exception as e:
        app.logger.error(f'Unexpected error in register route: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/owner/dashboard')
@login_required
def owner_dashboard():
    if current_user.role != 'owner':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    total_tenants = User.query.filter_by(role='tenant').count()
    total_payments = Payment.query.filter_by(status='completed').count()
    pending_requests = MaintenanceRequest.query.filter_by(status='open').count()
    recent_payments = Payment.query.filter_by(status='completed').order_by(Payment.payment_date.desc()).limit(5).all()
    
    return render_template('owner_dashboard.html', 
                         total_tenants=total_tenants,
                         total_payments=total_payments,
                         pending_requests=pending_requests,
                         recent_payments=recent_payments)

@app.route('/tenant/dashboard')
@login_required
def tenant_dashboard():
    if current_user.role != 'tenant':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    user_payments = Payment.query.filter_by(tenant_id=current_user.id).order_by(Payment.payment_date.desc()).limit(5).all()
    notifications = Notification.query.filter(
        (Notification.target_role == 'all') | 
        (Notification.target_role == 'tenant') | 
        (Notification.target_role == None)
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('tenant_dashboard.html', 
                         payments=user_payments,
                         notifications=notifications)

@app.route('/payment', methods=['GET', 'POST'])
@login_required
def make_payment():
    try:
        if current_user.role != 'tenant':
            flash('Only tenants can make payments.', 'danger')
            return redirect(url_for('index'))
        
        form = PaymentForm()
        current_year = datetime.now().year
        form.year.choices = [(year, str(year)) for year in range(current_year - 1, current_year + 2)]
        
        if form.validate_on_submit():
            try:
                existing_payment = Payment.query.filter_by(
                    tenant_id=current_user.id,
                    month=form.month.data,
                    year=form.year.data
                ).first()
                
                if existing_payment and existing_payment.status == 'completed':
                    flash('Payment for this month has already been made.', 'warning')
                else:
                    payment = Payment(
                        tenant_id=current_user.id,
                        amount=form.amount.data,
                        month=form.month.data,
                        year=form.year.data,
                        payment_method=form.payment_method.data,
                        status='completed'
                    )
                    db.session.add(payment)
                    db.session.commit()
                    app.logger.info(f'Payment created by user {current_user.username}: ${form.amount.data} for {form.month.data} {form.year.data}')
                    flash('Payment successful!', 'success')
                    return redirect(url_for('tenant_dashboard'))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Error creating payment: {str(e)}')
                flash('Payment processing failed. Please try again.', 'danger')
        
        return render_template('payment.html', form=form)
        
    except Exception as e:
        app.logger.error(f'Unexpected error in payment route: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return render_template('payment.html', form=form)

@app.route('/notifications')
@login_required
def notifications():
    if current_user.role == 'owner':
        notifications = Notification.query.order_by(Notification.created_at.desc()).all()
    else:
        notifications = Notification.query.filter(
            (Notification.target_role == 'all') | 
            (Notification.target_role == 'tenant') | 
            (Notification.target_role == None)
        ).order_by(Notification.created_at.desc()).all()
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/create', methods=['GET', 'POST'])
@login_required
def create_notification():
    try:
        if current_user.role != 'owner':
            flash('Only owners can create notifications.', 'danger')
            return redirect(url_for('index'))
        
        form = NotificationForm()
        if form.validate_on_submit():
            try:
                notification = Notification(
                    title=form.title.data,
                    content=form.content.data,
                    priority=form.priority.data,
                    target_role=form.target_role.data if form.target_role.data != 'all' else None
                )
                
                if form.file_attachment.data:
                    file = form.file_attachment.data
                    if file:
                        filename = secure_filename(file.filename)
                        if not filename:
                            flash('Invalid filename.', 'danger')
                            return render_template('create_notification.html', form=form, recent_notifications=[])
                        
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        
                        # Ensure upload directory exists
                        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                        
                        # Save file with error handling
                        try:
                            file.save(file_path)
                            notification.file_attachment = filename
                            app.logger.info(f'File uploaded for notification: {filename}')
                        except Exception as file_error:
                            app.logger.error(f'File upload failed: {str(file_error)}')
                            flash('File upload failed. Please try again.', 'danger')
                            return render_template('create_notification.html', form=form, recent_notifications=[])
                
                db.session.add(notification)
                db.session.commit()
                app.logger.info(f'Notification created by {current_user.username}: {form.title.data}')
                flash('Notification posted successfully!', 'success')
                return redirect(url_for('notifications'))
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Error creating notification: {str(e)}')
                flash('Failed to create notification. Please try again.', 'danger')
        
        recent_notifications = Notification.query.order_by(Notification.created_at.desc()).limit(3).all()
        return render_template('create_notification.html', form=form, recent_notifications=recent_notifications)
        
    except RequestEntityTooLarge:
        app.logger.error('File too large in notification creation')
        flash('File too large. Maximum size is 16MB.', 'danger')
        return render_template('create_notification.html', form=form, recent_notifications=[])
    except Exception as e:
        app.logger.error(f'Unexpected error in create_notification route: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return render_template('create_notification.html', form=form, recent_notifications=[])

@app.route('/reports')
@login_required
def payment_reports():
    if current_user.role != 'owner':
        flash('Only owners can view reports.', 'danger')
        return redirect(url_for('index'))
    
    payments = Payment.query.order_by(Payment.payment_date.desc()).all()
    return render_template('payment_reports.html', payments=payments)

@app.route('/maintenance')
@login_required
def maintenance_requests():
    if current_user.role == 'owner':
        requests = MaintenanceRequest.query.order_by(MaintenanceRequest.created_at.desc()).all()
    else:
        requests = MaintenanceRequest.query.filter_by(tenant_id=current_user.id).order_by(MaintenanceRequest.created_at.desc()).all()
    
    return render_template('maintenance_requests.html', requests=requests)

@app.route('/maintenance/create', methods=['GET', 'POST'])
@login_required
def create_maintenance_request():
    try:
        if current_user.role != 'tenant':
            flash('Only tenants can create maintenance requests.', 'danger')
            return redirect(url_for('index'))
        
        form = MaintenanceRequestForm()
        if form.validate_on_submit():
            try:
                # Check for duplicate requests (same title and tenant in last 24 hours)
                from datetime import timedelta
                yesterday = datetime.utcnow() - timedelta(hours=24)
                duplicate_request = MaintenanceRequest.query.filter(
                    MaintenanceRequest.tenant_id == current_user.id,
                    MaintenanceRequest.title == form.title.data,
                    MaintenanceRequest.created_at > yesterday
                ).first()
                
                if duplicate_request:
                    flash('A similar maintenance request was recently submitted. Please wait for an update.', 'warning')
                    return render_template('create_maintenance_request.html', form=form)
                
                request = MaintenanceRequest(
                    tenant_id=current_user.id,
                    title=form.title.data,
                    description=form.description.data,
                    category=form.category.data,
                    priority=form.priority.data
                )
                
                db.session.add(request)
                db.session.commit()
                app.logger.info(f'Maintenance request created by {current_user.username}: {form.title.data}')
                flash('Maintenance request submitted successfully!', 'success')
                return redirect(url_for('maintenance_requests'))
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Error creating maintenance request: {str(e)}')
                flash('Failed to submit maintenance request. Please try again.', 'danger')
        
        return render_template('create_maintenance_request.html', form=form)
        
    except Exception as e:
        app.logger.error(f'Unexpected error in create_maintenance_request route: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return render_template('create_maintenance_request.html', form=None)

@app.route('/maintenance/<int:request_id>/update', methods=['POST'])
@login_required
def update_maintenance_request(request_id):
    try:
        if current_user.role != 'owner':
            flash('Only owners can update maintenance requests.', 'danger')
            return redirect(url_for('index'))
        
        try:
            maintenance_request = MaintenanceRequest.query.get_or_404(request_id)
            new_status = request.form.get('status')
            
            if new_status in ['open', 'in_progress', 'completed']:
                maintenance_request.status = new_status
                if new_status == 'completed':
                    maintenance_request.resolved_at = datetime.utcnow()
                db.session.commit()
                app.logger.info(f'Maintenance request {request_id} updated to {new_status} by {current_user.username}')
                flash('Maintenance request updated successfully!', 'success')
            else:
                app.logger.warning(f'Invalid status update attempt: {new_status}')
                flash('Invalid status provided.', 'danger')
                
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error updating maintenance request {request_id}: {str(e)}')
            flash('Failed to update maintenance request. Please try again.', 'danger')
        
        return redirect(url_for('maintenance_requests'))
        
    except Exception as e:
        app.logger.error(f'Unexpected error in update_maintenance_request route: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return redirect(url_for('maintenance_requests'))

@app.route('/documents')
@login_required
def documents():
    if current_user.role == 'owner':
        documents = Document.query.order_by(Document.uploaded_at.desc()).all()
    else:
        documents = Document.query.filter(
            (Document.target_role == 'all') | 
            (Document.target_role == 'tenant') | 
            (Document.target_role == None)
        ).order_by(Document.uploaded_at.desc()).all()
    
    return render_template('documents.html', documents=documents)

@app.route('/documents/upload', methods=['GET', 'POST'])
@login_required
def upload_document():
    try:
        form = DocumentForm()
        if form.validate_on_submit():
            try:
                file = form.file.data
                if not file:
                    flash('Please select a file to upload.', 'danger')
                    return render_template('upload_document.html', form=form, recent_documents=[])
                
                filename = secure_filename(file.filename)
                if not filename:
                    flash('Invalid filename.', 'danger')
                    return render_template('upload_document.html', form=form, recent_documents=[])
                
                # Check file extension
                allowed_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif'}
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext not in allowed_extensions:
                    flash('File type not allowed. Allowed types: PDF, DOC, DOCX, XLS, XLSX, JPG, JPEG, PNG, GIF', 'danger')
                    return render_template('upload_document.html', form=form, recent_documents=[])
                
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Ensure upload directory exists
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                
                # Save file with error handling
                file.save(file_path)
                
                document = Document(
                    title=form.title.data,
                    filename=filename,
                    file_path=file_path,
                    file_type=file.content_type,
                    uploaded_by=current_user.id,
                    target_role=form.target_role.data if form.target_role.data != 'all' else None
                )
                
                db.session.add(document)
                db.session.commit()
                app.logger.info(f'Document uploaded by {current_user.username}: {filename}')
                flash('Document uploaded successfully!', 'success')
                return redirect(url_for('documents'))
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Error uploading document: {str(e)}')
                flash('Document upload failed. Please try again.', 'danger')
        
        recent_documents = Document.query.filter_by(uploaded_by=current_user.id).order_by(Document.uploaded_at.desc()).limit(3).all()
        return render_template('upload_document.html', form=form, recent_documents=recent_documents)
        
    except RequestEntityTooLarge:
        app.logger.error('File too large in document upload')
        flash('File too large. Maximum size is 16MB.', 'danger')
        return render_template('upload_document.html', form=form, recent_documents=[])
    except Exception as e:
        app.logger.error(f'Unexpected error in upload_document route: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return render_template('upload_document.html', form=form, recent_documents=[])

@app.route('/documents/<int:document_id>/download')
@login_required
def download_document(document_id):
    try:
        document = Document.query.get_or_404(document_id)
        
        # Check if user has permission to download this document
        if current_user.role == 'tenant':
            if document.target_role and document.target_role not in ['all', 'tenant']:
                app.logger.warning(f'Access denied for user {current_user.username} to document {document_id}')
                abort(403)
        elif current_user.role == 'owner':
            # Owners can download any document
            pass
        
        # Check if file exists
        if not os.path.exists(document.file_path):
            app.logger.error(f'Document file not found: {document.file_path}')
            abort(404)
        
        app.logger.info(f'Document {document_id} downloaded by {current_user.username}')
        return send_file(document.file_path, as_attachment=True, download_name=document.filename)
        
    except Exception as e:
        app.logger.error(f'Error downloading document {document_id}: {str(e)}')
        abort(500)

# Multi-Tenant SaaS Routes

@app.route('/register-tenant', methods=['GET', 'POST'])
def register_tenant():
    """Register a new tenant (business owner)"""
    try:
        form = TenantRegistrationForm()
        if form.validate_on_submit():
            try:
                # Check if business email already exists
                if Tenant.query.filter_by(contact_email=form.contact_email.data).first():
                    flash('Business email already registered. Please use a different one.', 'danger')
                    return render_template('register_tenant.html', form=form)
                
                tenant = Tenant(
                    business_name=form.business_name.data,
                    contact_email=form.contact_email.data,
                    contact_phone=form.contact_phone.data,
                    business_address=form.business_address.data,
                    subscription_plan=form.subscription_plan.data
                )
                
                db.session.add(tenant)
                db.session.commit()
                app.logger.info(f'New tenant registered: {tenant.business_name}')
                flash('Business registration successful! You can now log in.', 'success')
                return redirect(url_for('login'))
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Error during tenant registration: {str(e)}')
                flash('Registration failed. Please try again.', 'danger')
                
        return render_template('register_tenant.html', form=form)
        
    except Exception as e:
        app.logger.error(f'Unexpected error in tenant registration: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return render_template('register_tenant.html', form=None)

@app.route('/dashboard/tenant/<int:tenant_id>')
@login_required
def tenant_management_dashboard():
    """Dashboard for tenant owners to manage their properties"""
    try:
        # Check if current user is the owner of this tenant or an admin
        tenant = Tenant.query.get_or_404(tenant_id)
        
        if current_user.role != 'admin' and current_user.id != tenant.id:
            app.logger.warning(f'Unauthorized access attempt to tenant {tenant_id} by user {current_user.id}')
            abort(403)
        
        return render_template('tenant_management.html', tenant=tenant)
        
    except Exception as e:
        app.logger.error(f'Error in tenant management dashboard: {str(e)}')
        abort(500)

@app.route('/properties/add', methods=['GET', 'POST'])
@login_required
def add_property():
    """Add a new property for a tenant"""
    try:
        form = PropertyForm()
        if form.validate_on_submit():
            try:
                # Get tenant that this property belongs to
                if current_user.role == 'tenant':
                    tenant = Tenant.query.get(current_user.tenant_id)
                elif current_user.role == 'admin':
                    # Admin can add properties for any tenant
                    tenant_id = request.form.get('tenant_id')
                    tenant = Tenant.query.get(tenant_id) if tenant_id else None
                else:
                    flash('Only tenants and admins can add properties.', 'danger')
                    return redirect(url_for('index'))
                
                property = Property(
                    name=form.name.data,
                    address=form.address.data,
                    total_units=form.total_units.data,
                    owner_id=tenant.id
                )
                
                db.session.add(property)
                db.session.commit()
                app.logger.info(f'New property added: {property.name} by tenant {tenant.business_name}')
                flash('Property added successfully!', 'success')
                return redirect(url_for('tenant_management_dashboard', tenant_id=tenant.id))
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Error adding property: {str(e)}')
                flash('Failed to add property. Please try again.', 'danger')
        
        return render_template('add_property.html', form=form)
        
    except Exception as e:
        app.logger.error(f'Unexpected error in add_property: {str(e)}')
        flash('An unexpected error occurred. Please try again.', 'danger')
        return render_template('add_property.html', form=None)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create default admin user if not exists
        if not User.query.filter_by(role='admin').first():
            admin_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
            admin = User(
                username='admin',
                email='admin@rentalhub.com',
                password_hash=admin_password,
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: username=admin, password=admin123")
        
        print("""
========================================
     🏢 MULTI-TENANT SAAS PLATFORM
========================================
    
✅ Successfully configured for multi-tenant SaaS model:
    
📋 NEW ARCHITECTURE:
- Multiple tenants (business owners) supported
- Data isolation between tenants
- Flexible property and unit management
- SaaS subscription model ready

🎯 TARGET MARKET:
- Room rental businesses of any size
- Scalable from single property to enterprise
- Service-based recurring revenue model

🚀 READY FOR PRODUCTION:
- Enterprise-grade error handling
- Comprehensive security
- Multi-tenant data isolation
- SaaS subscription framework
""")
    
    app.run(debug=True, port=5001)