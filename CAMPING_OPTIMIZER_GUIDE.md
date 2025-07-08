# Gorilla Camping Optimizer - User Guide

## Overview
The Gorilla Camping Optimizer is an AI-powered tool that analyzes your camping setup and provides personalized recommendations for optimization. It features dual AI integration, Bluetooth device scanning, and comprehensive setup analysis.

## Features

### 🤖 Dual AI Integration
- **Free Users**: Google Gemini AI (3 queries per session)
- **Pro Users**: OpenAI GPT-3.5 (unlimited queries)

### 🏕️ Camping Setup Analysis
The optimizer analyzes multiple factors to provide a comprehensive score:

#### Setup Types Supported:
- Van Life
- Tent Camping
- RV/Motorhome
- Fifth Wheel
- Truck Camper

#### Power Source Options:
- Solar Panels
- Generator
- Shore Power
- Battery Bank Only
- Hybrid System

#### Camping Styles:
- Boondocking/Wild Camping
- Developed Campgrounds
- Mixed (Both)
- Urban/Stealth

#### Budget Ranges:
- Budget-Conscious ($0-500)
- Moderate ($500-2000)
- Premium ($2000+)

### 📱 Bluetooth Device Integration
The system can simulate scanning for and integrating with smart camping devices:
- Power stations (e.g., Jackery Explorer series)
- Weather monitors
- Tire pressure monitoring systems
- Solar charge controllers
- Tank level monitors

### 🎯 Optimization Scoring
The algorithm weights different aspects of your camping setup:
- Setup type compatibility (15-25 points)
- Power system efficiency (8-15 points)
- Electrical capacity (8-15 points)
- Location suitability (12-20 points)
- Budget optimization (10-15 points)

Maximum score: 100 points

## How to Use

### 1. Access the Optimizer
Navigate to `/optimizer` on the Gorilla Camping site.

### 2. Fill Out Your Setup
Complete the form with your camping preferences:
- Select your setup type
- Choose your primary power source
- Enter available amps
- Select camping style
- Choose budget range
- Check relevant activities

### 3. Get Your Score
Click "Optimize My Setup 🚀" to receive:
- Overall optimization score (0-100)
- Personalized recommendations
- Optimization tips
- Bluetooth device suggestions

### 4. Scan for Devices
Use "Scan Bluetooth Devices 📱" to discover compatible smart camping gear in your area.

### 5. Ask the AI
Use the AI assistant to get specific advice about your setup. Pro users get access to more advanced OpenAI models.

## Pro Upgrade
Demo upgrade codes for testing:
- `GORILLA2025`
- `PROCAMP`
- `DEMO123`

Pro features include:
- Unlimited AI queries with OpenAI GPT
- Advanced optimization algorithms
- Priority Bluetooth device recommendations
- Enhanced analysis and reporting

## API Endpoints

### POST /api/preferences
Save user camping preferences
```json
{
  "setup_type": "van",
  "power_type": "solar", 
  "available_amps": 30,
  "location_type": "boondocking",
  "budget_range": "medium"
}
```

### POST /api/optimize
Get AI-powered camping advice with setup analysis
```json
{
  "query": "What solar setup do I need?",
  "preferences": { /* user preferences */ }
}
```

### POST /api/bluetooth-scan
Simulate Bluetooth device discovery
Returns list of discovered camping devices with status information.

### POST /api/pro-upgrade
Upgrade to Pro features using upgrade code
```json
{
  "upgrade_code": "DEMO123"
}
```

## Technical Implementation

### Scoring Algorithm
The camping score is calculated by evaluating:
1. Setup type compatibility with use case
2. Power system efficiency and sustainability
3. Electrical capacity vs. needs
4. Location type suitability
5. Budget optimization for value

### AI Integration
- **Gemini**: Used for free tier with 3 query limit
- **OpenAI**: Used for Pro tier with unlimited queries
- Context includes user preferences and optimization data

### Bluetooth Simulation
- Simulates discovering common camping devices
- Returns realistic device data (battery levels, temperatures, etc.)
- Provides integration recommendations based on setup type

## Future Enhancements
- Real Bluetooth device integration
- GPS-based campground recommendations
- Weather integration for route planning
- Gear marketplace integration
- Community features for sharing setups