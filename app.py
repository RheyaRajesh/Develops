import streamlit as st
import time
import random
import math
import collections
import uuid
import json
from datetime import datetime, timedelta

# ==========================================
# CORE BACKEND LOGIC (Pure Python, No DB)
# ==========================================

# Constants for Decision Types
DECISION_ALLOW = "ALLOW"
DECISION_THROTTLE = "THROTTLE"
DECISION_BLOCK = "BLOCK"
DECISION_FLAG_SALES = "FLAG_SALES"

class TrialUser:
    def __init__(self, tenant_id, user_id, user_type="NORMAL"):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_type = user_type  # NORMAL, ABUSIVE, HIGH_VALUE
        self.created_at = time.time()
        self.events = []
        
        # Behavioral Fingerprint
        self.api_count = 0
        self.feature_sequence = []
        self.last_active = time.time()
        self.session_durations = []
        
        # ROI & Cost Metrics
        self.estimated_cost = 0.0
        self.feature_value = 0.0
        self.abuse_score = 0.0
        self.roi_score = 0.0
        self.current_decision = DECISION_ALLOW
        self.reasons = []

    def add_event(self, event_type, resource_id=None, cost=0.0, value=0.0):
        now = time.time()
        self.events.append({
            "timestamp": now,
            "type": event_type,
            "resource": resource_id
        })
        
        # Update Behavioral Signals
        self.api_count += 1
        self.feature_sequence.append(event_type)
        if len(self.feature_sequence) > 10:
            self.feature_sequence.pop(0)
            
        time_since_last = now - self.last_active
        if time_since_last > 300: # New session after 5 mins
            self.session_durations.append(0)
        elif self.session_durations:
             self.session_durations[-1] += time_since_last
             
        self.last_active = now
        
        # Update ROI basics
        self.estimated_cost += cost
        self.feature_value += value

class TenantConfig:
    def __init__(self, name):
        self.name = name
        # Detection Thresholds
        self.max_api_rate = 50.0  # req/min
        self.max_cost_per_session = 10.0
        self.abuse_threshold = 0.7
        self.roi_min_threshold = 0.0
        # Weights
        self.weight_abuse = 0.5
        self.weight_cost = 0.3
        self.weight_value = 0.2

class ResourceMonitor:
    def __init__(self):
        # resource_id -> list of timestamps
        self.usage_log = collections.defaultdict(list)
        self.drain_alerts = {}

    def log_usage(self, resource_id):
        now = time.time()
        self.usage_log[resource_id].append(now)
        # Cleanup old logs (>1 min)
        self.usage_log[resource_id] = [t for t in self.usage_log[resource_id] if now - t < 60]

    def get_load(self, resource_id):
        return len(self.usage_log[resource_id])

class TrialGuardEngine:
    def __init__(self):
        if 'users' not in st.session_state:
            st.session_state.users = {}
        if 'tenants' not in st.session_state:
            st.session_state.tenants = {
                "Tenant_A": TenantConfig("Tenant_A"),
                "Tenant_B": TenantConfig("Tenant_B")
            }
        if 'resource_monitor' not in st.session_state:
            st.session_state.resource_monitor = ResourceMonitor()
        if 'stats' not in st.session_state:
            st.session_state.stats = {
                "total_events": 0,
                "blocked_events": 0,
                "revenue_saved": 0.0,
                "cost_saved": 0.0
            }

    @property
    def users(self):
        return st.session_state.users

    @property
    def tenants(self):
        return st.session_state.tenants

    @property
    def resource_monitor(self):
        return st.session_state.resource_monitor

    def process_event(self, tenant_id, user_id, event_type, resource_id=None, user_type_simulation="NORMAL"):
        # 1. Get or Create User
        if user_id not in self.users:
            self.users[user_id] = TrialUser(tenant_id, user_id, user_type_simulation)
        
        user = self.users[user_id]
        tenant = self.tenants[tenant_id]
        
        # Simulating cost/value based on event type
        cost = random.uniform(0.1, 0.5) if event_type == "API_CALL" else 0.05
        value = random.uniform(0.5, 2.0) if event_type == "CHECKOUT_ATTEMPT" else 0.1
        
        if resource_id:
            self.resource_monitor.log_usage(resource_id)
            # High resource usage increases cost significantly
            if self.resource_monitor.get_load(resource_id) > 50:
                 cost *= 2.0

        # 2. Update User State
        user.add_event(event_type, resource_id, cost, value)
        
        # 3. Calculate Scores (The Core Logic)
        self._calculate_scores(user, tenant)
        
        # 4. Make Decision
        decision, reasons = self._make_decision(user, tenant)
        user.current_decision = decision
        user.reasons = reasons
        
        # 5. Update Global Stats
        st.session_state.stats["total_events"] += 1
        if decision == DECISION_BLOCK:
            st.session_state.stats["blocked_events"] += 1
            st.session_state.stats["cost_saved"] += cost
        elif decision == DECISION_FLAG_SALES:
             st.session_state.stats["revenue_saved"] += (value * 0.1) # Pretend conversion value

        return decision

    def _calculate_scores(self, user, tenant):
        # A. Abuse Score Calculation
        # Signals: API Rate, Resource Spam, Anomaly Sequence
        
        # Simple rate check (events per minute approx)
        # Using a simplistic sliding window approx for this demo
        duration_mins = max((time.time() - user.created_at) / 60.0, 0.1)
        api_rate = user.api_count / duration_mins
        
        raw_abuse_score = 0.0
        if api_rate > tenant.max_api_rate:
            raw_abuse_score += 0.4
        
        # Check for repetitive sequences (naive)
        if len(user.feature_sequence) >= 5 and len(set(user.feature_sequence[-5:])) == 1:
            raw_abuse_score += 0.3
            
        # Resource drain contribution
        if user.estimated_cost > tenant.max_cost_per_session:
            raw_abuse_score += 0.4
            
        user.abuse_score = min(raw_abuse_score, 1.0)
        
        # B. ROI Score Calculation
        # ROI = (Potential Value - Cost) * (1 - AbuseProb) - normalized
        # A simplified formula for the demo:
        
        net_value = user.feature_value - user.estimated_cost
        risk_factor = 1.0 - user.abuse_score
        
        user.roi_score = net_value * risk_factor

    def _make_decision(self, user, tenant):
        reasons = []
        
        # 1. Check Abuse
        if user.abuse_score >= tenant.abuse_threshold:
            # High Abuse
            if user.roi_score < -5.0:
                reasons.append(f"Critical Abuse Score ({user.abuse_score:.2f})")
                reasons.append(f"Negative ROI ({user.roi_score:.2f})")
                return DECISION_BLOCK, reasons
            elif user.roi_score > 5.0:
                # High abuse but high value? Suspicious but maybe throttle + sales
                reasons.append("High Volume but High Value")
                return DECISION_THROTTLE, reasons
            else:
                 reasons.append("Abuse Threshold Exceeded")
                 return DECISION_BLOCK, reasons

        # 2. Check Resource Drain (Shared)
        # If the user is hitting hot resources
        if user.events:
            last_resource = user.events[-1]['resource']
            if last_resource and self.resource_monitor.get_load(last_resource) > 100:
                reasons.append(f"Resource {last_resource} Overloaded")
                return DECISION_THROTTLE, reasons

        # 3. Check Sales Opportunity
        if user.roi_score > 10.0 and user.abuse_score < 0.2:
            reasons.append("High ROI User")
            return DECISION_FLAG_SALES, reasons

        return DECISION_ALLOW, ["Normal Behavior"]

# ==========================================
# SIMULATION ENGINE
# ==========================================

def run_simulation(engine):
    # Determine number of events to simulate
    num_events = random.randint(5, 20)
    
    tenants = list(engine.tenants.keys())
    event_types = ["LOGIN", "VIEW_DASHBOARD", "API_CALL", "EXPORT_DATA", "CHECKOUT_ATTEMPT"]
    resources = ["DB_SHARD_1", "API_GATEWAY", "EXPORT_WORKER", "AUTH_SERVICE"]
    
    logs = []
    
    for _ in range(num_events):
        tenant_id = random.choice(tenants)
        
        # Pick a user profile type
        rand = random.random()
        if rand < 0.7:
            u_type = "NORMAL"
            u_base = "msg_user"
        elif rand < 0.90:
            u_type = "ABUSIVE" # Bot / Scraper
            u_base = "bad_actor"
        else:
            u_type = "HIGH_VALUE" # Power user
            u_base = "vip_lead"
            
        # Create a semi-consistent user ID for this run
        user_suffix = random.randint(1, 5) # Small pool to show aggregation
        user_id = f"{u_base}_{user_suffix}"
        
        # Bias behavior based on type
        if u_type == "ABUSIVE":
            e_type = "API_CALL" # Spamming API
            res = "EXPORT_WORKER" # Hitting heavy resource
        elif u_type == "HIGH_VALUE":
            e_type = random.choice(["CHECKOUT_ATTEMPT", "VIEW_DASHBOARD"])
            res = "API_GATEWAY"
        else:
            e_type = random.choice(event_types)
            res = random.choice(resources)
            
        decision = engine.process_event(tenant_id, user_id, e_type, res, u_type)
        logs.append(f"[{tenant_id}] User {user_id} ({u_type}) -> {e_type} on {res} : {decision}")
        
    return logs

# ==========================================
# STREAMLIT UI
# ==========================================

def main():
    st.set_page_config(page_title="TrialGuard SaaS Protection", layout="wide", page_icon="🛡️")
    
    # Initialize Engine
    engine = TrialGuardEngine()
    
    # --- Sidebar ---
    st.sidebar.title("🛡️ TrialGuard")
    st.sidebar.markdown("Revenue Protection Platform")
    
    page = st.sidebar.radio("Navigation", [
        "Overview Dashboard",
        "Trial User Analyzer",
        "Resource Drain Monitor",
        "Tenant Configuration"
    ])
    
    st.sidebar.divider()
    st.sidebar.subheader("Simulation Control")
    if st.sidebar.button("Run Traffic Simulation", type="primary"):
        with st.spinner("Simulating events..."):
            logs = run_simulation(engine)
            st.session_state.sim_logs = logs
            time.sleep(0.5) # UX pause
        st.sidebar.success(f"Processed {len(logs)} events")
        
    if 'sim_logs' in st.session_state and st.session_state.sim_logs:
        with st.sidebar.expander("Recent Activity Log", expanded=False):
            for l in st.session_state.sim_logs[-10:]:
                st.caption(l)

    # --- Pages ---
    
    if page == "Overview Dashboard":
        render_dashboard(engine)
    elif page == "Trial User Analyzer":
        render_analyzer(engine)
    elif page == "Resource Drain Monitor":
        render_resource_monitor(engine)
    elif page == "Tenant Configuration":
        render_configuration(engine)

def render_dashboard(engine):
    st.title("Platform Overview")
    
    # Top Metrics
    stats = st.session_state.stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Trials", len(engine.users))
    
    abuse_rate = 0
    if stats["total_events"] > 0:
        abuse_rate = (stats["blocked_events"] / stats["total_events"]) * 100
        
    c2.metric("Block Rate", f"{abuse_rate:.1f}%")
    c3.metric("Est. Cost Saved", f"${stats['cost_saved']:.2f}")
    c4.metric("Rev Opportunity", f"${stats['revenue_saved']:.2f}")
    
    st.divider()
    
    # Recent Decisions Table
    st.subheader("Live Traffic Decisions")
    
    # Convert users dict to list for display
    # Showing most recent users
    user_list = list(engine.users.values())
    user_list.sort(key=lambda u: u.last_active, reverse=True)
    
    data = []
    for u in user_list[:10]:
        data.append({
            "Tenant": u.tenant_id,
            "User ID": u.user_id,
            "Type": u.user_type,
            "Abuse Score": f"{u.abuse_score:.2f}",
            "ROI Score": f"{u.roi_score:.2f}",
            "Decision": u.current_decision,
            "Reason": ", ".join(u.reasons) if u.reasons else "-"
        })
        
    st.dataframe(data, use_container_width=True)

def render_analyzer(engine):
    st.title("Trial User Analyzer")
    
    # Selector
    user_ids = list(engine.users.keys())
    if not user_ids:
        st.info("No trial users detected yet. Run the simulation!")
        return
        
    selected_id = st.selectbox("Select User to Analyze", user_ids)
    user = engine.users[selected_id]
    
    # Profile Header
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.metric("Abuse Risk", f"{user.abuse_score:.2f}", delta_color="inverse")
    with c2:
        decision_color = "red" if user.current_decision == DECISION_BLOCK else "green"
        st.markdown(f"### Current Status: :{decision_color}[{user.current_decision}]")
        st.caption(f"Tenant: {user.tenant_id} | Type: {user.user_type}")
    with c3:
        st.metric("ROI Score", f"{user.roi_score:.2f}")
        
    st.divider()
    
    # Detailed fingerprint
    c_left, c_right = st.columns(2)
    
    with c_left:
        st.subheader("Behavioral Signals")
        st.write(f"**API Count:** {user.api_count}")
        st.write(f"**Est. Resource Cost:** ${user.estimated_cost:.2f}")
        st.write("**Feature Sequence (Recent):**")
        st.code(" -> ".join(user.feature_sequence))

    with c_right:
        st.subheader("Decision Explanation")
        if user.reasons:
            for r in user.reasons:
                st.warning(f"⚠️ {r}")
        else:
            st.success("✅ No issues detected.")
            
        st.subheader("ROI Analysis")
        chart_val = (user.roi_score + 10) / 20 # Normalize roughly for progress bar
        chart_val = max(0.0, min(1.0, chart_val))
        st.progress(chart_val, text="ROI Potential")
        st.caption("Lower (Left) = Unprofitable/Risky | Higher (Right) = High Conversion Value")

def render_resource_monitor(engine):
    st.title("Resource Drain Detection")
    st.markdown("Monitoring backend resources for 'Fan-in' attacks and exhaustion.")
    
    monitor = engine.resource_monitor
    resources = monitor.usage_log.keys()
    
    if not resources:
        st.info("No resources accessed yet.")
        return
        
    cols = st.columns(3)
    for idx, res in enumerate(resources):
        load = monitor.get_load(res)
        with cols[idx % 3]:
            st.metric(label=res, value=f"{load} req/min")
            if load > 50:
                st.error("🔥 HIGH LOAD DETECTED")
            elif load > 20:
                st.warning("⚠️ Elevated Traffic")
            else:
                st.success("Normal Operation")
                
    st.divider()
    st.subheader("Drain Topology")
    st.caption("Visualizing user-to-resource mapping (Simulated)")
    st.bar_chart({r: monitor.get_load(r) for r in resources})

def render_configuration(engine):
    st.title("Tenant Configuration")
    
    tenant_names = list(engine.tenants.keys())
    selected_tenant = st.selectbox("Select Tenant", tenant_names)
    config = engine.tenants[selected_tenant]
    
    st.subheader(f"Rules for {config.name}")
    
    with st.form("config_form"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Thresholds")
            new_rate = st.slider("Max API Rate (req/min)", 10.0, 200.0, config.max_api_rate)
            new_abuse = st.slider("Abuse Score Threshold (0-1)", 0.1, 1.0, config.abuse_threshold)
            
        with c2:
            st.markdown("#### Cost Weights")
            new_w_abuse = st.number_input("Abuse Weight", 0.0, 1.0, config.weight_abuse)
            new_w_cost = st.number_input("Cost Weight", 0.0, 1.0, config.weight_cost)
            
        submitted = st.form_submit_button("Save Configuration")
        if submitted:
            config.max_api_rate = new_rate
            config.abuse_threshold = new_abuse
            config.weight_abuse = new_w_abuse
            config.weight_cost = new_w_cost
            st.success("Configuration updated successfully!")

if __name__ == "__main__":
    main()
