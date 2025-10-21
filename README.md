# Buddy Crocker - Recipe Management Platform

A web application that helps home cooks discover, create, and organize recipes while managing their kitchen pantry and dietary restrictions. Built for anyone who wants to simplify meal planning and make cooking more accessible.

## Live Application

Visit the app at: **https://buddy-crocker-web.onrender.com**

## Key Features (Note: some features are not yet implemented)

- **Smart Pantry Management** - Track ingredients you have on hand and easily add new ones with calorie and allergen information
- **Recipe Creation & Sharing** - Build your own digital cookbook with custom recipes and detailed instructions
- **Allergen-Aware Search** - Filter recipes based on dietary restrictions and allergen information
- **Ingredient Tracking** - View detailed nutritional information and see which recipes use specific ingredients
- **Personalized Profiles** - Save your allergen preferences to automatically filter recipes that are safe for you
- **Responsive Design** - Works seamlessly on desktop, tablet, and mobile devices

## How to Use 

1. Visit https://buddy-crocker-web.onrender.com
2. Create an account or log in to get started
3. Build your pantry by adding ingredients you have in your kitchen
4. Browse existing recipes or create your own with the "Add Recipe" feature
5. Search for recipes and filter by allergens to find meals that work for you
6. Click on any ingredient or recipe to view detailed information
7. Manage your dietary restrictions in your profile settings

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


Buddy Crocker is a Django web application developed by Team 3 for a Fall 2025 course project (CS4300). It's a recipe management and meal planning platform designed to help users cook smarter by managing their pantry ingredients and discovering recipes based on what they have available.

Core Features
Pantry Management: Users can add, view, and manage ingredients in their virtual pantry, including nutritional information (calories) and allergen tracking.

Recipe Search: A feature (currently stubbed) that will allow users to find recipes based on ingredients in their pantry.

Recipe Management: Users can add, view, edit, and delete recipes with ingredients and cooking instructions.

User Profiles: Authentication system with login, logout, and registration functionality.

Allergen Tracking: The system tracks allergens for both ingredients and recipes to help users with dietary restrictions.