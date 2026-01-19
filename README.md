# Rental Management System

A comprehensive Flask-based rental management web application for apartment owners and tenants.

## Features

### For Owners
- **Dashboard**: Overview of tenants, payments, and maintenance requests
- **Payment Reports**: Track and export rent payments with filtering options
- **Notifications**: Send announcements and important updates to tenants
- **Maintenance Management**: View and update tenant maintenance requests
- **Document Management**: Upload and share documents with tenants
- **User Management**: Monitor tenant accounts and activities

### For Tenants
- **Personal Dashboard**: View payment history and notifications
- **Online Payments**: Make rent payments securely
- **Maintenance Requests**: Submit and track maintenance issues
- **Document Access**: View shared documents and announcements
- **Communication**: Receive notifications from property owner

### Additional Features
- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile
- **Role-Based Access**: Secure authentication for owners and tenants
- **File Upload System**: Support for documents, images, and attachments
- **Real-Time Updates**: Dynamic status tracking for payments and requests
- **Data Export**: Generate reports in Excel and PDF formats
- **Security**: Password hashing, CSRF protection, and secure file handling

## Technology Stack

- **Backend**: Flask (Python Web Framework)
- **Database**: SQLAlchemy with SQLite (configurable for PostgreSQL/MySQL)
- **Authentication**: Flask-Login with bcrypt password hashing
- **Forms**: Flask-WTF with WTForms validation
- **Frontend**: Bootstrap 5 with Font Awesome icons
- **File Handling**: Werkzeug for secure file uploads

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd rentalapp
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize the database**:
   ```bash
   python app.py
   ```
   This will automatically create the database and default admin account.

## Usage

### Default Accounts
- **Owner**: Username: `admin`, Password: `admin123`
- **Tenants**: Register through the application

### Running the Application
```bash
python app.py
```
The application will be available at `http://localhost:5000`

## Configuration

### Environment Variables
- `SECRET_KEY`: Flask secret key for session management
- `DATABASE_URL`: Database connection string
- `FLASK_ENV`: Environment mode (development/production)

### Database Configuration
The application uses SQLite by default but can be configured for PostgreSQL or MySQL by updating the `DATABASE_URL` environment variable.

## Project Structure

```
rentalapp/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables
├── uploads/              # File upload directory
├── static/              # Static files (CSS, JS)
├── templates/           # HTML templates
│   ├── base.html       # Base template
│   ├── login.html      # Login page
│   ├── register.html   # Registration page
│   ├── owner_dashboard.html
│   ├── tenant_dashboard.html
│   ├── payment.html
│   ├── notifications.html
│   ├── payment_reports.html
│   ├── maintenance_requests.html
│   ├── documents.html
│   └── ...
└── rental.db           # SQLite database (auto-generated)
```

## Security Features

- **Password Security**: All passwords are hashed using bcrypt
- **CSRF Protection**: All forms protected with CSRF tokens
- **File Upload Security**: Secure filename handling and type validation
- **Role-Based Access**: Proper authorization checks for all routes
- **Session Management**: Secure session handling with Flask-Login

## Production Deployment

For production deployment:

1. **Use a production database** (PostgreSQL/MySQL recommended)
2. **Set up proper WSGI server** (Gunicorn/uWSGI)
3. **Configure reverse proxy** (Nginx/Apache)
4. **Enable HTTPS** with SSL certificates
5. **Set up proper logging** and monitoring
6. **Regular database backups**

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For support and questions, please open an issue in the repository or contact the development team.

---

**Note**: This is a comprehensive rental management system designed for small to medium-sized apartment complexes. For larger properties or additional features, consider extending the application with more advanced functionality.