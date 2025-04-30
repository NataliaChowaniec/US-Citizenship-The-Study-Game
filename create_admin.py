from main import app
from models import db, User
from werkzeug.security import generate_password_hash

def create_admin_user():
    """Create an admin user with elevated privileges"""
    with app.app_context():
        admin = User.query.filter_by(email='admin1@example.com').first()
        
        if not admin:
            new_admin = User(
                username='admin1',
                email='admin1@example.com',
                password_hash=generate_password_hash('adminpass'),
                state='NY',
                is_admin=True  # This sets admin privileges
            )
            db.session.add(new_admin)
            db.session.commit()
            print('Admin user created successfully')
        else:
            # Update existing user to be admin if they aren't
            if not admin.is_admin:
                admin.is_admin = True
                db.session.commit()
                print('Existing user promoted to admin')
            else:
                print('is_Admin user already exists')

if __name__ == "__main__":
    create_admin_user()