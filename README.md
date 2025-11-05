# Buddy Crocker - Recipe Management Platform

A web application that helps home cooks discover, create, and organize recipes while managing their kitchen pantry and dietary restrictions. Built for anyone who wants to simplify meal planning and make cooking more accessible.

## Live Application

Visit the app at: **https://buddy-crocker-web-qxxd.onrender.com**

## Key Features (Note: some features are not yet implemented)

- **Smart Pantry Management** - Track ingredients you have on hand and easily add new ones with calorie and allergen information
- **Recipe Creation & Sharing** - Build your own digital cookbook with custom recipes and detailed instructions
- **Allergen-Aware Search** - Filter recipes based on dietary restrictions and allergen information
- **Ingredient Tracking** - View detailed nutritional information and see which recipes use specific ingredients
- **Personalized Profiles** - Save your allergen preferences to automatically filter recipes that are safe for you
- **Responsive Design** - Works seamlessly on desktop, tablet, and mobile devices

## How to Use 

1. Visit https://buddy-crocker-web-qxxd.onrender.com
2. Create an account or log in to get started
3. Build your pantry by adding ingredients you have in your kitchen
4. Browse existing recipes or create your own with the "Add Recipe" feature
5. Search for recipes and filter by allergens to find meals that work for you
6. Click on any ingredient or recipe to view detailed information
7. Manage your dietary restrictions in your profile settings

## Automated Superuser Setup (Production)

To enable secure admin access on Render without shell access, the app includes an automated Django management command that creates a superuser from environment variables during deployment.

### How it works

- On each deployment, the command `python manage.py ensure_superuser` runs automatically.
- It reads these environment variables from your Render dashboard:
  - `DJANGO_SUPERUSER_USERNAME` 
  - `DJANGO_SUPERUSER_EMAIL` 
  - `DJANGO_SUPERUSER_PASSWORD` 
- If a superuser with that username exists, it leaves it unchanged.
- If no such user exists, it creates the superuser account.
- This approach avoids storing credentials in code or Git and requires no manual intervention.

### Environment Variable Setup

**Important:** These variables should **only** be set in the Render environment variables dashboard for production. Do **NOT** add them to your local `.env` file.

### Deployment Integration

The deploy process runs the command during build, as configured in `build.sh`:
    python manage.py migrate
    python manage.py ensure_superuser
    python manage.py collectstatic --noinput

### Accessing the Admin Interface

Once deployed, you can access the Django Admin interface at:
**https://buddy-crocker-web-qxxd.onrender.com/admin**
Log in with the superuser credentials you configured.

### Troubleshooting

- If the admin login fails, verify the environment variables are set correctly in Render dashboard.
- Locally, you can test superuser creation by exporting environment variables in your shell before running:
    export DJANGO_SUPERUSER_USERNAME=admin
    export DJANGO_SUPERUSER_EMAIL=admin@buddycrocker.com
    export DJANGO_SUPERUSER_PASSWORD=YourTestPassword123!
    python manage.py ensure_superuser       

- Remember the command will not overwrite an existing superuser with the same username.


## Technologies

- **Backend**: Django 5.2, Python 3.12
- **Database**: PostgreSQL (Production), SQLite (Development)
- **Frontend**: HTML5, CSS3, Custom Styling
- **Deployment**: Render
- **Additional Tools**: Gunicorn, WhiteNoise, Django REST Framework

## Project Status

**Current Version**: 1.0 (Beta)

### Upcoming Features
- Recipe search by pantry contents (see what you can make with what you have)
- Enhanced allergen filtering with visual warnings
- User authentication and personalized recipe collections
- Recipe ratings and reviews
- Grocery list generation from recipes
- Social sharing capabilities
- Recipe import from external sources

## Project Context

Developed for **CS4300 - Software Engineering at UCCS** by Team 3 during Fall 2025.

This project demonstrates full-stack web development skills including database design, user authentication, RESTful API development, and cloud deployment.

## Support

Questions or feedback? Contact us:
- GitHub Issues: [Report a bug or request a feature](https://github.com/mckennaded/Buddy_Crocker_CS4300/issues)
- Project Repository: [View the code](https://github.com/mckennaded/Buddy_Crocker_CS4300)

## Team

Developed by Team 3:
- **Ben W.** - Backend Development & Database Architecture
- **Brianne L.** - Project Management, Architecture & Testing
- **Cindy K.** - Frontend Development
- **Mckenna D.** - UI/UX Design & User Profiles/Permissions

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Built with ❤️ for home cooks everywhere*