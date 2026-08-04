# DeepChest - AI-Powered Chest X-Ray Diagnostic System

DeepChest is a comprehensive Flask-based medical web application that provides AI-assisted chest X-ray diagnostics using deep learning. The system integrates TensorFlow/Keras models with Grad-CAM visualization to detect COVID-19, Pneumonia, Tuberculosis, and Normal chest conditions. It includes complete clinic management functionality for patients, doctors, and clinic administrators.

## Features

### Core Functionality
- **AI Diagnosis**: Deep learning model for chest X-ray analysis with Grad-CAM heatmap visualization
- **Multi-User System**: Role-based access for Patients, Doctors, and Clinic Administrators
- **Report Generation**: Automated PDF report creation with X-ray images and AI predictions
- **Appointment Management**: Comprehensive scheduling system with conflict detection
- **Search Functionality**: Global search across appointments, reports, and patients
- **Notification System**: Automated notifications for appointments and report updates

### User Roles

#### Patient Features
- Book and manage appointments
- View medical reports with AI diagnosis
- Message doctors
- Add child patients
- Account management
- Search appointments and reports by date, symptoms, or month/year

#### Doctor Features
- View and manage appointments
- Access patient records
- Generate AI-powered diagnostic reports with Grad-CAM visualization
- Upload and analyze chest X-rays
- Search patients, appointments, and reports
- Account management

#### Clinic Administrator Features
- Manage clinic information
- Oversee all appointments and reports
- Manage doctor and patient accounts
- Book appointments for patients
- Delete expired reports and data
- User account administration

## Technology Stack

- **Backend**: Flask 3.1.2
- **Database**: MySQL (mysql-connector-python)
- **AI/ML**: TensorFlow 2.20.0, Keras
- **Image Processing**: OpenCV, Pillow, scikit-image
- **PDF Generation**: ReportLab
- **Cloud**: AWS SDK (boto3) for potential S3/SES integration
- **Server**: Gunicorn for production deployment

## Installation

### Prerequisites
- Python 3.8+
- MySQL Server
- Virtual environment (recommended)

### Setup Steps

1. **Clone the repository:**
   ```powershell
   cd "c:\Users\16047\Desktop\DeepChest Local"
   ```

2. **Create and activate virtual environment:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirement.txt
   ```

4. **Database Setup:**
   - Create MySQL database named `DeepChest`
   - Import the schema: `mysql -u root -p DeepChest < DeepChest.sql`
   - Update database credentials in `app.py`:
     ```python
     db_config = {
         'host': 'localhost',
         'user': 'root',
         'password': 'your_password',
         'database': 'DeepChest'
     }
     ```

5. **AI Model:**
   - Ensure `model_1.keras` is present in the root directory
   - Model trained to detect: COVID-19, Normal, Pneumonia, Tuberculosis

6. **Run the application:**
   ```powershell
   .venv\Scripts\python.exe app.py
   ```
   Or use the VS Code task: "Run Flask App"

7. **Access the application:**
   - Open browser: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Project Structure

```
DeepChest Local/
├── app.py                      # Main Flask application (3200+ lines)
├── model_1.keras               # Pre-trained AI model
├── DeepChest.sql              # Database schema
├── requirement.txt            # Python dependencies
├── Kerascode.md              # AI model documentation
├── AI_Model/                  # Jupyter notebooks for model training
│   ├── DeepChest-1stModel.ipynb
│   └── Model_Run.ipynb
├── Services/                  # Production deployment configs
│   ├── Ai_service.py
│   ├── DeepChest.conf
│   ├── DeepChest.service
│   └── gunicorn.service
├── static/                    # CSS and uploaded files
│   ├── admin.css
│   ├── doctor.css
│   ├── patient.css
│   ├── style.css
│   ├── logostyle.css
│   └── uploads/              # User-uploaded X-ray images
├── templates/                # HTML templates
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   ├── clinic_signup.html
│   ├── search_results.html
│   ├── navigationbase.html
│   ├── patient/              # Patient-specific pages
│   ├── doctor/               # Doctor-specific pages
│   └── clinic_admin/         # Admin-specific pages
└── .venv/                    # Virtual environment
```

## Key Routes

### Public Routes
- `/` - Home page
- `/login` - User login
- `/signup` - Patient registration
- `/clinic_signup` - Clinic registration
- `/search` - Global search

### Patient Routes
- `/patient_home` - Dashboard
- `/patient/appointments` - View/manage appointments
- `/patient/book-appointment` - Schedule new appointment
- `/patient/reports` - View medical reports
- `/patient/messages` - Message doctors
- `/patient/account` - Account management
- `/patient/add-child` - Add dependent patients

### Doctor Routes
- `/doctor_home` - Dashboard
- `/doctor/appointments` - View appointments
- `/doctor/patients` - Patient list
- `/doctor/reports` - Report management
- `/doctor/ai_diagnosis` - AI X-ray analysis
- `/doctor/account` - Account settings

### Admin Routes
- `/admin_home` - Dashboard
- `/admin/appointments` - Appointment management
- `/admin/manage_clinic` - Clinic settings
- `/admin/manage_reports` - Report oversight
- `/admin/ManageAccount` - User management

## AI Model Details

- **Architecture**: Convolutional Neural Network (CNN)
- **Input**: 224x224x3 RGB chest X-ray images
- **Output Classes**: COVID19, NORMAL, PNEUMONIA, TUBERCULOSIS
- **Visualization**: Grad-CAM heatmaps highlight diagnostic regions
- **Model File**: `model_1.keras` (TensorFlow/Keras format)

## GitHub Pages + Render setup

This repository is prepared for a two-part deployment:
- GitHub Pages hosts the static landing page.
- Render hosts the Flask app and AI backend.

### 1. Deploy the Flask app on Render
1. Create a new Render Web Service.
2. Connect this GitHub repository.
3. Choose the service type for the Flask app.
4. Set the start command to:
   ```bash
   gunicorn app:app
   ```
5. Add environment variables such as SECRET_KEY and your database settings.

### 2. Enable GitHub Pages without Actions
1. Go to your GitHub repository settings.
2. Open Pages.
3. Select the branch-based deployment source.
4. Choose the main branch and the docs folder as the publish source.
5. Save the settings.

### 3. Point the landing page to your Render backend
Open [docs/config.js](docs/config.js) and replace the placeholder URL with your Render app URL, for example:
```js
window.API_BASE_URL = 'https://your-render-app.onrender.com';
```

The static page will test the backend health endpoint automatically.

## Security Notes

⚠️ **Important**: Before deploying to production:
- Change `app.secret_key` in `app.py`
- Update database credentials
- Enable HTTPS
- Implement proper authentication/authorization
- Set `debug=False` in production
- Configure environment variables for sensitive data

## Database Schema

The application uses MySQL with tables for:
- `patient` - Patient records
- `doctor` - Doctor profiles
- `clinicadmin` - Administrator accounts
- `clinic` - Clinic information
- `appointments` - Appointment scheduling
- `Reports` - Medical reports with X-ray data
- `xrays` - X-ray image storage
- `messages` - Patient-doctor messaging
- `notifications` - System notifications

## Development

To run in development mode:
```powershell
.venv\Scripts\python.exe app.py
```

For production deployment with Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

See `Services/` directory for systemd service configurations.




