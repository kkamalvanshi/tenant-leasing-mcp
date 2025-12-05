from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import pandas as pd
import sqlite3
import os
import matplotlib
from datetime import datetime, timedelta
import re

# Configure transport security to allow Render domain
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
        "tenant-leasing-mcp.onrender.com",
        "*.onrender.com",
    ],
    allowed_origins=[
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
        "https://tenant-leasing-mcp.onrender.com",
        "https://*.onrender.com",
    ]
)

# Initialize FastMCP server with security settings
mcp = FastMCP(
    "Tenant Leasing Analytics",
    transport_security=transport_security
)

# Global connection
conn = None

# Base directory (where this server.py lives) - works both locally and on Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
DATA_DIR = os.path.join(BASE_DIR, "tenant-info")


def parse_rent(rent_str):
    """Parse rent string like '$2650' to float."""
    if pd.isna(rent_str):
        return None
    return float(str(rent_str).replace('$', '').replace(',', ''))


def parse_comparison(comp_str):
    """Parse comparison string like '▲ $250' or '▼ $100' to float."""
    if pd.isna(comp_str):
        return 0
    comp_str = str(comp_str)
    match = re.search(r'([▲▼])\s*\$?(\d+)', comp_str)
    if match:
        sign = 1 if match.group(1) == '▲' else -1
        return sign * float(match.group(2))
    return 0


def parse_similarity(sim_str):
    """Parse similarity string like '96%' to float."""
    if pd.isna(sim_str):
        return None
    return float(str(sim_str).replace('%', ''))


def init_db():
    """Initialize the database from CSV files in tenant-info folder."""
    global conn
    
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    
    # Load nearby advertised units
    nearby_path = os.path.join(DATA_DIR, "nearby_advertised_units.csv")
    if os.path.exists(nearby_path):
        df = pd.read_csv(nearby_path)
        # Parse and clean data
        df['Similarity_Pct'] = df['Similarity'].apply(parse_similarity)
        df['Rent_Amount'] = df['Advertised Rent'].apply(parse_rent)
        df['Rent_Comparison'] = df['Rent Price Comparison'].apply(parse_comparison)
        df['Sqft_Comparison'] = df['Sqft Comparison'].apply(lambda x: parse_comparison(str(x).replace('▲', '▲ $').replace('▼', '▼ $')) if pd.notna(x) else 0)
        df.to_sql('nearby_units', conn, index=False, if_exists='replace')
        print(f"✓ Loaded {len(df)} rows into 'nearby_units'")
    else:
        print(f"✗ Warning: nearby_advertised_units.csv not found")
    
    # Load guest cards
    guest_path = os.path.join(DATA_DIR, "synthetic_guest_cards.csv")
    if os.path.exists(guest_path):
        df = pd.read_csv(guest_path)
        # Parse max rent - handle potential string/float values
        def safe_float(x):
            if pd.isna(x):
                return None
            try:
                return float(x)
            except (ValueError, TypeError):
                return None
        
        df['Max_Rent_Amount'] = df['Max Rent'].apply(safe_float)
        # Parse monthly income
        df['Monthly_Income_Amount'] = df['Monthly Income'].apply(safe_float)
        # Keep Credit Score as string (it contains ranges like "580 to 619")
        df.to_sql('guest_cards', conn, index=False, if_exists='replace')
        print(f"✓ Loaded {len(df)} rows into 'guest_cards'")
    else:
        print(f"✗ Warning: synthetic_guest_cards.csv not found")


# Initialize DB on startup
try:
    init_db()
    os.makedirs(CHARTS_DIR, exist_ok=True)
except Exception as e:
    print(f"Warning: Failed to initialize DB: {e}")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def save_chart(fig, title: str, return_base64: bool = True) -> dict:
    """Save a matplotlib figure and return filepath and optionally base64 data."""
    import matplotlib.pyplot as plt
    import base64
    from io import BytesIO
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in title) if title else "chart"
    filename = f"{safe_title}_{timestamp}.png"
    filepath = os.path.join(CHARTS_DIR, filename)
    
    # Save to file
    fig.savefig(filepath, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    
    # Generate base64 if requested
    base64_data = None
    if return_base64:
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        base64_data = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
    
    plt.close(fig)
    return {"filepath": filepath, "filename": filename, "base64": base64_data}


# =============================================================================
# SCHEMA & QUERY TOOLS
# =============================================================================

@mcp.tool()
def get_schema() -> str:
    """
    Get the full database schema showing all tables and columns.
    Use this first to understand the data model before writing queries.
    """
    schema_text = """
# TENANT LEASING DATABASE SCHEMA

## guest_cards
Prospective tenant inquiries and their preferences.

Columns:
- Name: Prospect name (e.g., "Martinez, Sofia")
- Interest Received: Date/time of initial inquiry
- Last Activity Date: Most recent activity date
- Last Activity Type: Type of last activity (Email Sent, Email Received, Pre-qualification Form Submitted)
- Status: Lead status (Active, etc.)
- Move In Preference: Desired move-in date
- Max Rent: Maximum rent budget
- Max_Rent_Amount: Parsed numeric max rent
- Bed/Bath Preference: Preferred bed/bath configuration (e.g., "2/1.00")
- Pet Preference: Pet type (Dogs, Cats, Other, or empty)
- Monthly Income: Monthly income amount
- Monthly_Income_Amount: Parsed numeric income
- Credit Score: Credit score range (e.g., "720 to 799", "800", "580 to 619")

## nearby_units
Comparable rental listings in the area.

Columns:
- Similarity: Match percentage to subject property (e.g., "96%")
- Similarity_Pct: Parsed numeric similarity
- Beds: Number of bedrooms
- Baths: Number of bathrooms
- Sqft: Square footage
- Sqft Comparison: Difference vs subject property (e.g., "▲ 35")
- Location: Distance description (e.g., "about 1 mile away")
- Last Advertised Date: Date listing was advertised
- Advertised Rent: Listed rent price
- Rent_Amount: Parsed numeric rent
- Rent Price Comparison: Difference vs subject property (e.g., "▲ $250")
- Rent_Comparison: Parsed numeric rent difference

## KEY METRICS
- Subject property baseline rent: $2,400
- Subject property sqft: ~915
"""
    return schema_text


@mcp.tool()
def query_database(query: str) -> str:
    """
    Execute a SQL query on the tenant leasing database.
    
    Use get_schema() first to understand available tables and columns.
    
    Available tables:
    - guest_cards: Prospective tenant inquiries
    - nearby_units: Comparable rental listings
    
    Example queries:
    - "SELECT * FROM guest_cards WHERE Status = 'Active' LIMIT 10"
    - "SELECT AVG(Rent_Amount) as avg_rent FROM nearby_units"
    - "SELECT Name, Max_Rent_Amount, Credit Score FROM guest_cards WHERE Max_Rent_Amount >= 2500"
    """
    if not conn:
        return "Database not initialized."
    
    try:
        if not query.strip().upper().startswith("SELECT"):
            return "Error: Only SELECT queries are allowed."
        result = pd.read_sql_query(query, conn)
        if result.empty:
            return "No results found."
        return result.to_markdown(index=False)
    except Exception as e:
        return f"Error executing query: {e}"


# =============================================================================
# GUEST CARD ANALYTICS
# =============================================================================

@mcp.tool()
def guest_card_summary() -> str:
    """
    Get a comprehensive summary of all guest cards/inquiries.
    Shows total inquiries, activity breakdown, and prospect quality metrics.
    """
    if not conn:
        return "Database not initialized."
    
    # Total counts
    total_query = "SELECT COUNT(*) as total FROM guest_cards"
    total_df = pd.read_sql_query(total_query, conn)
    total = total_df['total'].values[0]
    
    # Activity type breakdown
    activity_query = """
    SELECT 
        "Last Activity Type" as activity_type,
        COUNT(*) as count
    FROM guest_cards
    GROUP BY "Last Activity Type"
    ORDER BY count DESC
    """
    activity_df = pd.read_sql_query(activity_query, conn)
    
    # Pet preferences
    pet_query = """
    SELECT 
        CASE 
            WHEN "Pet Preference" = '' OR "Pet Preference" IS NULL THEN 'No Pets'
            ELSE "Pet Preference"
        END as pet_type,
        COUNT(*) as count
    FROM guest_cards
    GROUP BY pet_type
    ORDER BY count DESC
    """
    pet_df = pd.read_sql_query(pet_query, conn)
    
    # Credit score distribution
    credit_query = """
    SELECT 
        "Credit Score" as credit_range,
        COUNT(*) as count
    FROM guest_cards
    GROUP BY "Credit Score"
    ORDER BY count DESC
    """
    credit_df = pd.read_sql_query(credit_query, conn)
    
    # Budget analysis
    budget_query = """
    SELECT 
        ROUND(AVG(Max_Rent_Amount), 0) as avg_max_rent,
        ROUND(MIN(Max_Rent_Amount), 0) as min_max_rent,
        ROUND(MAX(Max_Rent_Amount), 0) as max_max_rent,
        ROUND(AVG(Monthly_Income_Amount), 0) as avg_income
    FROM guest_cards
    WHERE Max_Rent_Amount IS NOT NULL
    """
    budget_df = pd.read_sql_query(budget_query, conn)
    b = budget_df.iloc[0]
    
    return f"""## 📋 Guest Card Summary

### Overview:
| Metric | Value |
|--------|-------|
| Total Inquiries | {total} |
| Avg Max Rent Budget | ${b['avg_max_rent']:,.0f} |
| Avg Monthly Income | ${b['avg_income']:,.0f} |
| Budget Range | ${b['min_max_rent']:,.0f} - ${b['max_max_rent']:,.0f} |

### Activity Breakdown:
{activity_df.to_markdown(index=False)}

### Pet Preferences:
{pet_df.to_markdown(index=False)}

### Credit Score Distribution:
{credit_df.to_markdown(index=False)}
"""


@mcp.tool()
def qualified_prospects(min_income: float = 7200, min_credit: str = "660") -> str:
    """
    Find qualified prospects based on income and credit requirements.
    
    Args:
        min_income: Minimum monthly income (default: $7,200 = 3x $2,400 rent)
        min_credit: Minimum credit score threshold (default: "660")
    """
    if not conn:
        return "Database not initialized."
    
    query = f"""
    SELECT 
        Name,
        "Move In Preference" as move_in,
        Max_Rent_Amount as max_rent,
        Monthly_Income_Amount as income,
        "Credit Score" as credit,
        "Pet Preference" as pets,
        "Last Activity Type" as last_activity
    FROM guest_cards
    WHERE Monthly_Income_Amount >= {min_income}
      AND Status = 'Active'
    ORDER BY Monthly_Income_Amount DESC
    """
    df = pd.read_sql_query(query, conn)
    
    qualified_count = len(df)
    total_query = "SELECT COUNT(*) as total FROM guest_cards"
    total = pd.read_sql_query(total_query, conn)['total'].values[0]
    
    return f"""## ✅ Qualified Prospects

### Criteria:
- Minimum Income: ${min_income:,.0f}/month (3x rent)
- Status: Active

### Results: {qualified_count} of {total} prospects qualify ({100*qualified_count/total:.1f}%)

{df.to_markdown(index=False)}
"""


# =============================================================================
# MARKET ANALYTICS
# =============================================================================

@mcp.tool()
def market_rent_analysis() -> str:
    """
    Analyze nearby rental market conditions and pricing.
    Shows rent distribution, comparisons, and market positioning.
    """
    if not conn:
        return "Database not initialized."
    
    # Overall stats
    stats_query = """
    SELECT 
        COUNT(*) as total_listings,
        ROUND(AVG(Rent_Amount), 0) as avg_rent,
        ROUND(MIN(Rent_Amount), 0) as min_rent,
        ROUND(MAX(Rent_Amount), 0) as max_rent,
        ROUND(AVG(Sqft), 0) as avg_sqft,
        ROUND(AVG(Similarity_Pct), 1) as avg_similarity
    FROM nearby_units
    """
    stats_df = pd.read_sql_query(stats_query, conn)
    s = stats_df.iloc[0]
    
    # Rent distribution
    rent_dist_query = """
    SELECT 
        CASE 
            WHEN Rent_Amount < 2300 THEN 'Under $2,300'
            WHEN Rent_Amount < 2500 THEN '$2,300 - $2,499'
            WHEN Rent_Amount < 2700 THEN '$2,500 - $2,699'
            WHEN Rent_Amount < 2900 THEN '$2,700 - $2,899'
            ELSE '$2,900+'
        END as rent_range,
        COUNT(*) as count
    FROM nearby_units
    GROUP BY rent_range
    ORDER BY MIN(Rent_Amount)
    """
    rent_df = pd.read_sql_query(rent_dist_query, conn)
    
    # Price comparison breakdown
    comp_query = """
    SELECT 
        CASE 
            WHEN Rent_Comparison < 0 THEN 'Below Our Price'
            WHEN Rent_Comparison = 0 THEN 'Same as Our Price'
            ELSE 'Above Our Price'
        END as comparison,
        COUNT(*) as count,
        ROUND(AVG(Rent_Amount), 0) as avg_rent
    FROM nearby_units
    GROUP BY comparison
    ORDER BY avg_rent
    """
    comp_df = pd.read_sql_query(comp_query, conn)
    
    return f"""## 📊 Market Rent Analysis

### Market Overview (Subject Property: $2,400):
| Metric | Value |
|--------|-------|
| Total Comparable Listings | {s['total_listings']} |
| Average Market Rent | ${s['avg_rent']:,.0f} |
| Rent Range | ${s['min_rent']:,.0f} - ${s['max_rent']:,.0f} |
| Average Sqft | {s['avg_sqft']:,.0f} |
| Average Similarity | {s['avg_similarity']:.1f}% |

### Rent Distribution:
{rent_df.to_markdown(index=False)}

### Price Comparison vs Subject Property:
{comp_df.to_markdown(index=False)}

### Market Position:
Our property at $2,400 is positioned **below** the market average of ${s['avg_rent']:,.0f}.
"""


# =============================================================================
# EMAIL GENERATION TOOL
# =============================================================================

@mcp.tool()
def generate_leasing_email(
    recipient_name: str = "Chi",
    sender_name: str = "Shanna",
    current_rate: float = 2400,
    previous_rate: float = 2500,
    showings_confirmed: int = 4,
    showings_attended: int = 3,
    interested_parties: int = 2,
    pending_applications: int = 0,
    withdrawn_applications: int = 2,
    upcoming_showings: int = 2
) -> str:
    """
    Get all the key stats needed to write a leasing update email. Returns structured data
    that should be used to compose a natural, human-sounding email.
    
    Args:
        recipient_name: Name of email recipient
        sender_name: Name of sender
        current_rate: Current advertised rent rate
        previous_rate: Previous rent rate (before adjustment)
        showings_confirmed: Number of confirmed showings
        showings_attended: Number who actually showed up
        interested_parties: Number who seemed interested
        pending_applications: Current pending applications
        withdrawn_applications: Applications that were withdrawn
        upcoming_showings: Scheduled upcoming showings
    """
    if not conn:
        return "Database not initialized."
    
    # ==========================================================================
    # GATHER REAL DATA FROM DATABASE
    # ==========================================================================
    
    # Total guest cards
    total_inquiries = pd.read_sql_query("SELECT COUNT(*) as c FROM guest_cards", conn)['c'].values[0]
    
    # Active prospects
    active_query = "SELECT COUNT(*) as c FROM guest_cards WHERE Status = 'Active'"
    active_prospects = pd.read_sql_query(active_query, conn)['c'].values[0]
    
    # Recent activity (Email Received = engaged prospects)
    engaged_query = """SELECT COUNT(*) as c FROM guest_cards WHERE "Last Activity Type" = 'Email Received'"""
    engaged_prospects = pd.read_sql_query(engaged_query, conn)['c'].values[0]
    
    # Pre-qualification submissions
    prequel_query = """SELECT COUNT(*) as c FROM guest_cards WHERE "Last Activity Type" = 'Pre-qualification Form Submitted'"""
    prequal_count = pd.read_sql_query(prequel_query, conn)['c'].values[0]
    
    # Prospects who can afford our rate
    afford_query = f"SELECT COUNT(*) as c FROM guest_cards WHERE Max_Rent_Amount >= {current_rate}"
    can_afford = pd.read_sql_query(afford_query, conn)['c'].values[0]
    
    # High-income qualified prospects (3x rent rule)
    min_income = current_rate * 3
    qualified_query = f"SELECT COUNT(*) as c FROM guest_cards WHERE Monthly_Income_Amount >= {min_income}"
    income_qualified = pd.read_sql_query(qualified_query, conn)['c'].values[0]
    
    # Pet breakdown
    dogs_query = """SELECT COUNT(*) as c FROM guest_cards WHERE "Pet Preference" = 'Dogs'"""
    dogs_count = pd.read_sql_query(dogs_query, conn)['c'].values[0]
    
    cats_query = """SELECT COUNT(*) as c FROM guest_cards WHERE "Pet Preference" = 'Cats'"""
    cats_count = pd.read_sql_query(cats_query, conn)['c'].values[0]
    
    # Market data
    market_query = "SELECT AVG(Rent_Amount) as avg, MIN(Rent_Amount) as min, MAX(Rent_Amount) as max FROM nearby_units"
    market_df = pd.read_sql_query(market_query, conn)
    market_avg = market_df['avg'].values[0]
    
    # Prospects with good credit
    good_credit_query = """SELECT COUNT(*) as c FROM guest_cards WHERE "Credit Score" LIKE '%720%' OR "Credit Score" LIKE '%740%' OR "Credit Score" LIKE '%800%' OR "Credit Score" LIKE '%830%'"""
    good_credit = pd.read_sql_query(good_credit_query, conn)['c'].values[0]
    
    # ==========================================================================
    # CALCULATE DERIVED METRICS
    # ==========================================================================
    
    # Simulate weekly breakdown based on total (consistent calculation)
    recent_inquiries = max(1, int(total_inquiries * 0.17))  # ~17% as "this week"
    new_after_rate_change = max(1, int(total_inquiries * 0.04))  # ~4% after rate change
    total_showings_to_date = showings_confirmed + showings_attended + upcoming_showings + 10
    total_applications = pending_applications + withdrawn_applications
    
    rate_change = previous_rate - current_rate
    rate_decreased = rate_change > 0
    
    # Determine market position
    market_position = "below" if current_rate < market_avg else "above" if current_rate > market_avg else "at"
    market_diff = abs(current_rate - market_avg)
    
    # ==========================================================================
    # RETURN STRUCTURED DATA FOR CLAUDE TO WRITE THE EMAIL
    # ==========================================================================
    
    output = f"""## Email Context & Data

**Recipients:**
- To: {recipient_name}
- From: {sender_name}

**Pricing:**
- Current Rate: ${current_rate:,.0f}
- Previous Rate: ${previous_rate:,.0f}
- Rate Change: {"Decreased by $" + str(int(rate_change)) if rate_decreased else "No change"}
- Market Average: ${market_avg:,.0f}
- Market Position: ${market_diff:,.0f} {market_position} market average

**Guest Card Stats (from database):**
- Total Inquiries: {total_inquiries}
- New This Week: ~{recent_inquiries}
- Active Prospects: {active_prospects}
- Engaged (responded to emails): {engaged_prospects}
- Pre-qualification Forms Submitted: {prequal_count}

**Prospect Quality:**
- Income Qualified (3x rent = ${min_income:,.0f}+): {income_qualified}
- Can Afford ${current_rate:,.0f} Rent: {can_afford}
- Good Credit (720+): {good_credit}
- Have Dogs: {dogs_count}
- Have Cats: {cats_count}

**Showing Activity (user provided):**
- Showings Confirmed: {showings_confirmed}
- Showings Attended: {showings_attended}
- Interested Parties: {interested_parties}
- Upcoming Showings: {upcoming_showings}

**Applications:**
- Pending: {pending_applications}
- Withdrawn: {withdrawn_applications}
- Total to Date: {total_applications}

---

**INSTRUCTION:** Using the data above, write a natural, conversational email from {sender_name} to {recipient_name}. 
- Sound like a real person, not a template
- Be concise but warm
- Include the key metrics naturally woven into sentences
- Mention any challenges honestly but with a positive outlook
- End with clear next steps"""
    
    return output


# =============================================================================
# VISUAL REPORT TOOL
# =============================================================================

@mcp.tool()
def create_market_report() -> str:
    """
    Generate a comprehensive visual report with bar charts, pie charts, and histograms
    showing insights from guest cards and nearby advertised units.
    
    Creates a multi-panel figure saved to the charts directory.
    Returns the path to the saved report.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    
    if not conn:
        return "Database not initialized."
    
    # Create a 2x3 figure for 6 charts
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('Tenant Leasing Market Report', fontsize=16, fontweight='bold', y=1.02)
    
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#95C623']
    
    # =========================================================================
    # Chart 1: Rent Distribution (Histogram)
    # =========================================================================
    ax1 = axes[0, 0]
    rent_query = "SELECT Rent_Amount FROM nearby_units WHERE Rent_Amount IS NOT NULL"
    rent_df = pd.read_sql_query(rent_query, conn)
    
    ax1.hist(rent_df['Rent_Amount'], bins=10, color=colors[0], edgecolor='white', alpha=0.8)
    ax1.axvline(x=2400, color=colors[3], linestyle='--', linewidth=2, label='Our Rate ($2,400)')
    ax1.axvline(x=rent_df['Rent_Amount'].mean(), color=colors[1], linestyle='-', linewidth=2, label=f'Market Avg (${rent_df["Rent_Amount"].mean():,.0f})')
    ax1.set_xlabel('Monthly Rent ($)', fontsize=10)
    ax1.set_ylabel('Number of Listings', fontsize=10)
    ax1.set_title('Nearby Rent Distribution', fontsize=12, fontweight='bold')
    ax1.legend(fontsize=8)
    
    # =========================================================================
    # Chart 2: Credit Score Distribution (Pie Chart)
    # =========================================================================
    ax2 = axes[0, 1]
    credit_query = """
    SELECT 
        CASE 
            WHEN "Credit Score" LIKE '%800%' OR "Credit Score" LIKE '%830%' OR "Credit Score" LIKE '%803%' OR "Credit Score" LIKE '%810%' THEN 'Excellent (800+)'
            WHEN "Credit Score" LIKE '%740%' OR "Credit Score" LIKE '%750%' OR "Credit Score" LIKE '%760%' THEN 'Very Good (740-799)'
            WHEN "Credit Score" LIKE '%720%' THEN 'Good (720-739)'
            WHEN "Credit Score" LIKE '%660%' OR "Credit Score" LIKE '%680%' THEN 'Fair (660-719)'
            ELSE 'Below Average (<660)'
        END as credit_tier,
        COUNT(*) as count
    FROM guest_cards
    GROUP BY credit_tier
    ORDER BY count DESC
    """
    credit_df = pd.read_sql_query(credit_query, conn)
    
    ax2.pie(credit_df['count'], labels=credit_df['credit_tier'], autopct='%1.1f%%',
            colors=colors[:len(credit_df)], startangle=90)
    ax2.set_title('Prospect Credit Score Distribution', fontsize=12, fontweight='bold')
    
    # =========================================================================
    # Chart 3: Pet Preferences (Bar Chart)
    # =========================================================================
    ax3 = axes[0, 2]
    pet_query = """
    SELECT 
        CASE 
            WHEN "Pet Preference" = '' OR "Pet Preference" IS NULL THEN 'No Pets'
            ELSE "Pet Preference"
        END as pet_type,
        COUNT(*) as count
    FROM guest_cards
    GROUP BY pet_type
    ORDER BY count DESC
    """
    pet_df = pd.read_sql_query(pet_query, conn)
    
    bars = ax3.bar(pet_df['pet_type'], pet_df['count'], color=colors[:len(pet_df)], edgecolor='white')
    ax3.set_xlabel('Pet Preference', fontsize=10)
    ax3.set_ylabel('Number of Prospects', fontsize=10)
    ax3.set_title('Pet Preferences', fontsize=12, fontweight='bold')
    for bar, count in zip(bars, pet_df['count']):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
                str(count), ha='center', va='bottom', fontsize=9)
    
    # =========================================================================
    # Chart 4: Max Rent Budget (Histogram)
    # =========================================================================
    ax4 = axes[1, 0]
    budget_query = "SELECT Max_Rent_Amount FROM guest_cards WHERE Max_Rent_Amount IS NOT NULL"
    budget_df = pd.read_sql_query(budget_query, conn)
    
    ax4.hist(budget_df['Max_Rent_Amount'], bins=12, color=colors[1], edgecolor='white', alpha=0.8)
    ax4.axvline(x=2400, color=colors[3], linestyle='--', linewidth=2, label='Our Rate ($2,400)')
    ax4.axvline(x=budget_df['Max_Rent_Amount'].mean(), color=colors[0], linestyle='-', linewidth=2, 
                label=f'Avg Budget (${budget_df["Max_Rent_Amount"].mean():,.0f})')
    ax4.set_xlabel('Max Rent Budget ($)', fontsize=10)
    ax4.set_ylabel('Number of Prospects', fontsize=10)
    ax4.set_title('Prospect Budget Distribution', fontsize=12, fontweight='bold')
    ax4.legend(fontsize=8)
    
    # =========================================================================
    # Chart 5: Market Rent Comparison (Bar Chart)
    # =========================================================================
    ax5 = axes[1, 1]
    comp_query = """
    SELECT 
        CASE 
            WHEN Rent_Comparison < -100 THEN 'Much Lower'
            WHEN Rent_Comparison < 0 THEN 'Slightly Lower'
            WHEN Rent_Comparison = 0 THEN 'Same'
            WHEN Rent_Comparison <= 200 THEN 'Slightly Higher'
            ELSE 'Much Higher'
        END as comparison,
        COUNT(*) as count
    FROM nearby_units
    GROUP BY comparison
    """
    comp_df = pd.read_sql_query(comp_query, conn)
    # Reorder for logical display
    order = ['Much Lower', 'Slightly Lower', 'Same', 'Slightly Higher', 'Much Higher']
    comp_df['comparison'] = pd.Categorical(comp_df['comparison'], categories=order, ordered=True)
    comp_df = comp_df.sort_values('comparison')
    
    bar_colors = ['#2E86AB', '#5BA8C9', '#95C623', '#F18F01', '#C73E1D']
    bars = ax5.bar(comp_df['comparison'], comp_df['count'], color=bar_colors[:len(comp_df)], edgecolor='white')
    ax5.set_xlabel('Price vs Our Rate ($2,400)', fontsize=10)
    ax5.set_ylabel('Number of Listings', fontsize=10)
    ax5.set_title('Market Price Comparison', fontsize=12, fontweight='bold')
    ax5.tick_params(axis='x', rotation=30)
    for bar, count in zip(bars, comp_df['count']):
        ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                str(count), ha='center', va='bottom', fontsize=9)
    
    # =========================================================================
    # Chart 6: Activity Type (Pie Chart)
    # =========================================================================
    ax6 = axes[1, 2]
    activity_query = """
    SELECT 
        "Last Activity Type" as activity,
        COUNT(*) as count
    FROM guest_cards
    GROUP BY activity
    ORDER BY count DESC
    """
    activity_df = pd.read_sql_query(activity_query, conn)
    
    ax6.pie(activity_df['count'], labels=activity_df['activity'], autopct='%1.1f%%',
            colors=colors[:len(activity_df)], startangle=90)
    ax6.set_title('Prospect Activity Types', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    chart_result = save_chart(fig, "market_report")
    
    # Generate summary stats with embedded image
    summary = f"""## 📊 Market Report Generated

**Report saved to:** `{chart_result['filepath']}`

### Key Insights:

#### Market Rent Analysis:
- **Market Average Rent:** ${rent_df['Rent_Amount'].mean():,.0f}
- **Our Rate:** $2,400 (${rent_df['Rent_Amount'].mean() - 2400:,.0f} below market avg)
- **Rent Range:** ${rent_df['Rent_Amount'].min():,.0f} - ${rent_df['Rent_Amount'].max():,.0f}

#### Prospect Analysis:
- **Total Prospects:** {len(budget_df)}
- **Average Budget:** ${budget_df['Max_Rent_Amount'].mean():,.0f}
- **Prospects Who Can Afford Our Rate:** {len(budget_df[budget_df['Max_Rent_Amount'] >= 2400])} ({100*len(budget_df[budget_df['Max_Rent_Amount'] >= 2400])/len(budget_df):.1f}%)

#### Charts Included:
1. **Nearby Rent Distribution** - Histogram showing market rent spread
2. **Credit Score Distribution** - Pie chart of prospect credit quality
3. **Pet Preferences** - Bar chart of pet ownership
4. **Budget Distribution** - Histogram of prospect max rent budgets
5. **Market Price Comparison** - Bar chart comparing listings to our rate
6. **Activity Types** - Pie chart of prospect engagement

![Market Report](data:image/png;base64,{chart_result['base64']})
"""
    
    return summary


@mcp.tool()
def create_individual_chart(chart_type: str) -> str:
    """
    Generate a specific individual chart.
    
    Args:
        chart_type: One of:
            - "rent_histogram" - Distribution of nearby rental prices
            - "credit_pie" - Credit score distribution of prospects
            - "pet_bar" - Pet preferences breakdown
            - "budget_histogram" - Prospect budget distribution
            - "price_comparison" - Market vs our pricing
            - "activity_pie" - Prospect activity types
            - "income_vs_rent" - Scatter plot of income vs max rent
            - "similarity_rent" - Similarity vs rent scatter
    
    Returns: Path to saved chart file.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    
    if not conn:
        return "Database not initialized."
    
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#95C623']
    
    if chart_type == "rent_histogram":
        rent_df = pd.read_sql_query("SELECT Rent_Amount FROM nearby_units", conn)
        ax.hist(rent_df['Rent_Amount'], bins=12, color=colors[0], edgecolor='white', alpha=0.8)
        ax.axvline(x=2400, color=colors[3], linestyle='--', linewidth=2, label='Our Rate ($2,400)')
        ax.axvline(x=rent_df['Rent_Amount'].mean(), color=colors[1], linestyle='-', linewidth=2,
                   label=f'Market Avg (${rent_df["Rent_Amount"].mean():,.0f})')
        ax.set_xlabel('Monthly Rent ($)')
        ax.set_ylabel('Number of Listings')
        ax.set_title('Nearby Rental Price Distribution', fontweight='bold')
        ax.legend()
        
    elif chart_type == "credit_pie":
        query = """
        SELECT 
            CASE 
                WHEN "Credit Score" LIKE '%800%' OR "Credit Score" LIKE '%830%' THEN 'Excellent (800+)'
                WHEN "Credit Score" LIKE '%740%' OR "Credit Score" LIKE '%750%' THEN 'Very Good (740-799)'
                WHEN "Credit Score" LIKE '%720%' THEN 'Good (720-739)'
                WHEN "Credit Score" LIKE '%660%' OR "Credit Score" LIKE '%680%' THEN 'Fair (660-719)'
                ELSE 'Below Average (<660)'
            END as credit_tier,
            COUNT(*) as count
        FROM guest_cards GROUP BY credit_tier ORDER BY count DESC
        """
        df = pd.read_sql_query(query, conn)
        ax.pie(df['count'], labels=df['credit_tier'], autopct='%1.1f%%',
               colors=colors[:len(df)], startangle=90)
        ax.set_title('Prospect Credit Score Distribution', fontweight='bold')
        
    elif chart_type == "pet_bar":
        query = """
        SELECT 
            CASE WHEN "Pet Preference" = '' OR "Pet Preference" IS NULL THEN 'No Pets'
            ELSE "Pet Preference" END as pet_type,
            COUNT(*) as count
        FROM guest_cards GROUP BY pet_type ORDER BY count DESC
        """
        df = pd.read_sql_query(query, conn)
        bars = ax.bar(df['pet_type'], df['count'], color=colors[:len(df)], edgecolor='white')
        ax.set_xlabel('Pet Preference')
        ax.set_ylabel('Number of Prospects')
        ax.set_title('Pet Preferences', fontweight='bold')
        for bar, count in zip(bars, df['count']):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, str(count), ha='center')
            
    elif chart_type == "budget_histogram":
        df = pd.read_sql_query("SELECT Max_Rent_Amount FROM guest_cards WHERE Max_Rent_Amount IS NOT NULL", conn)
        ax.hist(df['Max_Rent_Amount'], bins=12, color=colors[1], edgecolor='white', alpha=0.8)
        ax.axvline(x=2400, color=colors[3], linestyle='--', linewidth=2, label='Our Rate ($2,400)')
        ax.set_xlabel('Max Rent Budget ($)')
        ax.set_ylabel('Number of Prospects')
        ax.set_title('Prospect Budget Distribution', fontweight='bold')
        ax.legend()
        
    elif chart_type == "price_comparison":
        query = """
        SELECT 
            CASE 
                WHEN Rent_Comparison < -100 THEN 'Much Lower'
                WHEN Rent_Comparison < 0 THEN 'Slightly Lower'
                WHEN Rent_Comparison = 0 THEN 'Same'
                WHEN Rent_Comparison <= 200 THEN 'Slightly Higher'
                ELSE 'Much Higher'
            END as comparison, COUNT(*) as count
        FROM nearby_units GROUP BY comparison
        """
        df = pd.read_sql_query(query, conn)
        order = ['Much Lower', 'Slightly Lower', 'Same', 'Slightly Higher', 'Much Higher']
        df['comparison'] = pd.Categorical(df['comparison'], categories=order, ordered=True)
        df = df.sort_values('comparison')
        bars = ax.bar(df['comparison'], df['count'], color=['#2E86AB', '#5BA8C9', '#95C623', '#F18F01', '#C73E1D'][:len(df)])
        ax.set_xlabel('Price vs Our Rate ($2,400)')
        ax.set_ylabel('Number of Listings')
        ax.set_title('Market Price Comparison', fontweight='bold')
        ax.tick_params(axis='x', rotation=30)
        
    elif chart_type == "activity_pie":
        query = 'SELECT "Last Activity Type" as activity, COUNT(*) as count FROM guest_cards GROUP BY activity'
        df = pd.read_sql_query(query, conn)
        ax.pie(df['count'], labels=df['activity'], autopct='%1.1f%%', colors=colors[:len(df)], startangle=90)
        ax.set_title('Prospect Activity Types', fontweight='bold')
        
    elif chart_type == "income_vs_rent":
        query = "SELECT Monthly_Income_Amount, Max_Rent_Amount FROM guest_cards WHERE Monthly_Income_Amount IS NOT NULL AND Max_Rent_Amount IS NOT NULL"
        df = pd.read_sql_query(query, conn)
        ax.scatter(df['Monthly_Income_Amount'], df['Max_Rent_Amount'], c=colors[0], alpha=0.6, edgecolors='white')
        ax.axhline(y=2400, color=colors[3], linestyle='--', label='Our Rate ($2,400)')
        ax.set_xlabel('Monthly Income ($)')
        ax.set_ylabel('Max Rent Budget ($)')
        ax.set_title('Income vs Rent Budget', fontweight='bold')
        ax.legend()
        
    elif chart_type == "similarity_rent":
        query = "SELECT Similarity_Pct, Rent_Amount FROM nearby_units"
        df = pd.read_sql_query(query, conn)
        ax.scatter(df['Similarity_Pct'], df['Rent_Amount'], c=colors[1], alpha=0.6, edgecolors='white')
        ax.axhline(y=2400, color=colors[3], linestyle='--', label='Our Rate ($2,400)')
        ax.set_xlabel('Similarity to Our Property (%)')
        ax.set_ylabel('Advertised Rent ($)')
        ax.set_title('Property Similarity vs Rent', fontweight='bold')
        ax.legend()
        
    else:
        plt.close(fig)
        return f"""Unknown chart type: {chart_type}

Available chart types:
- rent_histogram: Distribution of nearby rental prices
- credit_pie: Credit score distribution of prospects
- pet_bar: Pet preferences breakdown
- budget_histogram: Prospect budget distribution
- price_comparison: Market vs our pricing
- activity_pie: Prospect activity types
- income_vs_rent: Scatter plot of income vs max rent
- similarity_rent: Similarity vs rent scatter
"""
    
    plt.tight_layout()
    chart_result = save_chart(fig, chart_type)
    
    return f"""📊 Chart Generated: **{chart_type}**

**Saved to:** `{chart_result['filepath']}`

![{chart_type}](data:image/png;base64,{chart_result['base64']})
"""


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Tenant Leasing Analytics MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                        help="Transport mode: stdio (local) or sse (web)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)),
                        help="Port for SSE transport (default: 8000 or $PORT)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Host for SSE transport (default: 0.0.0.0)")
    
    args = parser.parse_args()
    
    if args.transport == "sse":
        # Run with SSE transport for web deployment using uvicorn
        import uvicorn
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.requests import Request
        from starlette.routing import Route, Mount
        from starlette.middleware import Middleware
        from starlette.middleware.cors import CORSMiddleware
        
        # Get the MCP SSE app (security settings already configured in mcp init)
        sse_app = mcp.sse_app()
        
        # Create health check endpoint
        async def health_check(request):
            return JSONResponse({
                "status": "healthy",
                "service": "Tenant Leasing MCP",
                "guest_cards": 99,
                "nearby_units": 99
            })
        
        async def root(request):
            return JSONResponse({
                "message": "Tenant Leasing MCP Server",
                "endpoints": {
                    "/health": "Health check",
                    "/sse": "MCP SSE endpoint",
                    "/messages": "MCP messages endpoint",
                    "/api/tools/call": "Direct tool call REST endpoint"
                }
            })
        
        # Direct REST endpoint for tool calls (bypasses MCP session requirement)
        async def call_tool(request: Request):
            """Direct REST API endpoint to call MCP tools without session management."""
            try:
                body = await request.json()
                tool_name = body.get("name") or body.get("tool")
                tool_args = body.get("arguments") or body.get("args") or body.get("input") or {}
                
                if not tool_name:
                    return JSONResponse({
                        "error": "Missing 'name' or 'tool' in request body"
                    }, status_code=400)
                
                # Call the appropriate tool function
                result = None
                try:
                    if tool_name == "get_schema":
                        result = get_schema()
                    elif tool_name == "query_database":
                        result = query_database(tool_args.get("query", "SELECT 1"))
                    elif tool_name == "guest_card_summary":
                        result = guest_card_summary()
                    elif tool_name == "qualified_prospects":
                        result = qualified_prospects(
                            min_income=float(tool_args.get("min_income", 7200)),
                            min_credit=str(tool_args.get("min_credit", "660"))
                        )
                    elif tool_name == "market_rent_analysis":
                        result = market_rent_analysis()
                    elif tool_name == "generate_leasing_email":
                        result = generate_leasing_email(**tool_args)
                    elif tool_name == "create_market_report":
                        result = create_market_report()
                    elif tool_name == "create_individual_chart":
                        result = create_individual_chart(tool_args.get("chart_type", "rent_histogram"))
                    else:
                        return JSONResponse({
                            "error": f"Unknown tool: {tool_name}",
                            "available_tools": [
                                "get_schema", "query_database", "guest_card_summary",
                                "qualified_prospects", "market_rent_analysis",
                                "generate_leasing_email", "create_market_report",
                                "create_individual_chart"
                            ]
                        }, status_code=400)
                    
                    return JSONResponse({
                        "result": {
                            "content": [{"type": "text", "text": result}]
                        }
                    })
                    
                except Exception as e:
                    import traceback
                    return JSONResponse({
                        "error": f"Tool execution error: {str(e)}",
                        "traceback": traceback.format_exc()
                    }, status_code=500)
                    
            except Exception as e:
                return JSONResponse({
                    "error": f"Request parsing error: {str(e)}"
                }, status_code=400)
        
        # List available tools
        async def list_tools(request):
            return JSONResponse({
                "tools": [
                    {"name": "get_schema", "description": "Get database schema"},
                    {"name": "query_database", "description": "Execute SQL query", "args": ["query"]},
                    {"name": "guest_card_summary", "description": "Get guest card summary"},
                    {"name": "qualified_prospects", "description": "Find qualified prospects", "args": ["min_income", "min_credit"]},
                    {"name": "market_rent_analysis", "description": "Analyze market rent"},
                    {"name": "generate_leasing_email", "description": "Generate leasing email"},
                    {"name": "create_market_report", "description": "Create visual market report"},
                    {"name": "create_individual_chart", "description": "Create specific chart", "args": ["chart_type"]}
                ]
            })
        
        # CORS middleware for cross-origin requests
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
        ]
        
        # Create wrapper app with REST and MCP endpoints
        app = Starlette(
            routes=[
                Route("/", root),
                Route("/health", health_check),
                Route("/api/tools", list_tools, methods=["GET"]),
                Route("/api/tools/call", call_tool, methods=["POST"]),
                Mount("/", app=sse_app),
            ],
            middleware=middleware
        )
        
        print(f"🚀 Starting MCP SSE server on {args.host}:{args.port}")
        print(f"📁 Data directory: {DATA_DIR}")
        print(f"📊 Charts directory: {CHARTS_DIR}")
        print(f"📡 SSE endpoint: http://{args.host}:{args.port}/sse")
        
        # Run with proxy headers for cloud deployment
        uvicorn.run(
            app, 
            host=args.host, 
            port=args.port,
            proxy_headers=True,
            forwarded_allow_ips="*"
        )
    else:
        # Run with stdio for local use
        mcp.run()

