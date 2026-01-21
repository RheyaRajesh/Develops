# TrialGuard

**TrialGuard** is a SaaS Trial Abuse Detection & Revenue Protection Platform designed to optimize trial profitability by balancing abuse risk, infrastructure cost, and conversion likelihood.

It allows SaaS companies to continuously decide whether to **Allow**, **Throttle**, **Block**, or **Flag** trial users based on:
-   **Behavioral Fingerprinting**: Tracking non-PII usage patterns.
-   **Resource Drain Detection**: Identifying shared resource exhaustion.
-   **ROI Scoring**: real-time calculation of value vs cost/risk.

## Features

-   **Multi-Tenant Architecture**: Logical separation for multiple customers.
-   **Dashboard**: Real-time admin interface built with Streamlit.
-   **Simulation Engine**: Built-in traffic generator to test detection logic with "Abusive", "Normal", and "High Value" user profiles.
-   **Pure Python Backend**: No external database or heavy dependencies required.

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/TrialGuard.git
    cd TrialGuard
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the application locally:

```bash
streamlit run app.py
```

Navigate to `http://localhost:8501` in your browser.

### Key Pages
-   **Overview Dashboard**: Monitoring stats and live decision feed.
-   **Trial User Analyzer**: Deep dive into specific user scores and reasons.
-   **Resource Drain Monitor**: Visualizing backend load.
-   **Tenant Configuration**: Adjusting thresholds and weights.

## License

[MIT](LICENSE)
