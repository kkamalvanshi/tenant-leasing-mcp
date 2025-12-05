# Tenant Leasing Analytics - MCP Server

A specialized MCP (Model Context Protocol) server for tenant leasing analytics, focused on guest card management and market rent comparisons.

## 📊 Data Architecture

This MCP server only uses data from the `tenant-info/` folder:

| Table | Description | Rows |
|-------|-------------|------|
| `guest_cards` | Prospective tenant inquiries with preferences | 100 |
| `nearby_units` | Comparable rental listings in the area | 100 |

## 🛠️ Available Tools

### Schema & Query
| Tool | Description |
|------|-------------|
| `get_schema()` | View database schema and column descriptions |
| `query_database(sql)` | Execute any SELECT query |

### Guest Card Analytics
| Tool | Description |
|------|-------------|
| `guest_card_summary()` | Comprehensive summary of all inquiries |
| `qualified_prospects(min_income, min_credit)` | Find prospects meeting criteria |

### Market Analytics
| Tool | Description |
|------|-------------|
| `market_rent_analysis()` | Analyze nearby rental market conditions |

### 📧 Email Generation
| Tool | Description |
|------|-------------|
| `generate_leasing_email(...)` | Create professional leasing update email |

### 📊 Visual Reports
| Tool | Description |
|------|-------------|
| `create_market_report()` | Full 6-chart visual report (bar, pie, histogram) |
| `create_individual_chart(type)` | Generate specific chart types |

## 📧 Email Generation

The `generate_leasing_email()` tool creates professional leasing update emails like:

```
Good Morning Chi,

Last week in total we received 17 inquiries and I had no groups confirm showings. 
As discussed, we decreased the rate to $2400 and have received 4 new inquiries...
```

Parameters:
- `recipient_name`: Email recipient
- `sender_name`: Your name
- `current_rate`: Current advertised rent
- `previous_rate`: Previous rent rate
- `showings_confirmed`: Number of confirmed showings
- `showings_attended`: Number who attended
- `interested_parties`: Number who seemed interested
- `pending_applications`: Current pending apps
- `withdrawn_applications`: Withdrawn apps
- `upcoming_showings`: Scheduled future showings

## 📊 Visual Reports

### Full Market Report (`create_market_report()`)
Generates a comprehensive 6-panel report including:
1. **Rent Distribution Histogram** - Nearby rental price spread
2. **Credit Score Pie Chart** - Prospect credit quality
3. **Pet Preferences Bar Chart** - Pet ownership breakdown
4. **Budget Distribution Histogram** - Prospect max rent budgets
5. **Price Comparison Bar Chart** - Market vs our rate
6. **Activity Types Pie Chart** - Prospect engagement

### Individual Charts (`create_individual_chart(type)`)
Available chart types:
- `rent_histogram` - Distribution of nearby rental prices
- `credit_pie` - Credit score distribution
- `pet_bar` - Pet preferences breakdown
- `budget_histogram` - Prospect budget distribution
- `price_comparison` - Market vs our pricing
- `activity_pie` - Prospect activity types
- `income_vs_rent` - Income vs max rent scatter
- `similarity_rent` - Property similarity vs rent scatter

## 🚀 Setup

### Prerequisites
- Python 3.10+
- `uv` package manager

### Installation

```bash
cd /Users/kkamalva/financial_analysis/MCP/kurt-data
uv sync
```

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tenant-leasing": {
      "command": "/Users/kkamalva/financial_analysis/MCP/kurt-data/run_server.sh"
    }
  }
}
```

## 💬 Example Questions

### Guest Card Questions
- "Show me a summary of all guest cards"
- "Find qualified prospects with income over $8,000"
- "What's the credit score distribution of our prospects?"

### Market Questions
- "Analyze the nearby rental market"
- "How does our price compare to the market?"
- "What's the average rent in the area?"

### Email & Reports
- "Generate a leasing update email for Chi"
- "Create a market report with charts"
- "Generate a rent histogram"

## 📁 Data Files

This MCP server is self-contained within the `kurt-data/` folder and only uses data from `tenant-info/`:

```
kurt-data/
├── server.py              ← MCP server
├── run_server.sh          ← Launch script
├── pyproject.toml         ← Dependencies
├── tenant-info/
│   ├── synthetic_guest_cards.csv
│   └── nearby_advertised_units.csv
└── charts/
    └── (generated visualizations)
```


