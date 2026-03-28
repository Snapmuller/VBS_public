import streamlit as st
import pandas as pd
import smtplib
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- DATABASE SETUP ---
Base = declarative_base()
engine = create_engine('sqlite:///vbs_database.db', connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Customer(Base):
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String)
    vehicles = relationship("Vehicle", back_populates="owner", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="customer", cascade="all, delete-orphan")

class Vehicle(Base):
    __tablename__ = 'vehicles'
    id = Column(Integer, primary_key=True)
    registration = Column(String, unique=True, nullable=False)
    make_model = Column(String, nullable=False)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    owner = relationship("Customer", back_populates="vehicles")
    bookings = relationship("Booking", back_populates="vehicle", cascade="all, delete-orphan")

class Garage(Base):
    __tablename__ = 'garages'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    bookings = relationship("Booking", back_populates="garage")

class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    vehicle_id = Column(Integer, ForeignKey('vehicles.id'), nullable=False)
    garage_id = Column(Integer, ForeignKey('garages.id'), nullable=False)
    job_title = Column(String, nullable=False)
    description = Column(Text)
    date = Column(DateTime, nullable=False)
    cost = Column(Float, nullable=False)
    status = Column(String, default="Confirmed")
    customer = relationship("Customer", back_populates="bookings")
    vehicle = relationship("Vehicle", back_populates="bookings")
    garage = relationship("Garage", back_populates="bookings")

Base.metadata.create_all(engine)

# --- IMPROVED EMAIL HELPER (FOR RAILWAY) ---
def send_confirmation_email(cust_email, cust_name, veh_reg, job, garage, date_obj, cost):
    try:
        # Pull and clean secrets
        s_user = str(st.secrets["emails"]["smtp_user"]).replace('"', '').replace(' ', '').strip()
        s_pass = str(st.secrets["emails"]["smtp_pass"]).replace('"', '').replace(' ', '').strip()
        s_server = str(st.secrets["emails"]["smtp_server"]).replace('"', '').replace(' ', '').strip()
        
        msg = MIMEMultipart()
        msg['From'] = f"VBS Pro <{s_user}>"
        msg['To'] = cust_email
        msg['Subject'] = f"Booking Confirmation: {veh_reg}"
        
        body = f"Hello {cust_name},\n\nYour booking for {veh_reg} is confirmed.\n\nDetails:\n- Job: {job}\n- Garage: {garage}\n- Date: {date_obj}\n- Cost: £{cost:.2f}\n\nThank you!"
        msg.attach(MIMEText(body, 'plain'))

        # TRY PORT 465 (SSL) - This is usually MORE RELIABLE on Railway/Cloud
        try:
            with smtplib.SMTP_SSL(s_server, 465, timeout=15) as server:
                server.login(s_user, s_pass)
                server.send_message(msg)
            return True
        except Exception as ssl_err:
            # FALLBACK TO PORT 587 (TLS)
            try:
                with smtplib.SMTP(s_server, 587, timeout=15) as server:
                    server.starttls()
                    server.login(s_user, s_pass)
                    server.send_message(msg)
                return True
            except Exception as tls_err:
                st.error(f"❌ Email Failed. SSL Error: {ssl_err} | TLS Error: {tls_err}")
                return False
    except Exception as e:
        st.error(f"❌ Secrets Error: {e}. Check your Railway Variables.")
        return False

# --- SIDEBAR WITH DIAGNOSTIC TOOL ---
with st.sidebar:
    st.title("🚗 VBS Pro")
    if st.button("📊 Dashboard", use_container_width=True): nav('dashboard')
    if st.button("👥 Customers", use_container_width=True): nav('customers')
    if st.button("🚗 Vehicles", use_container_width=True): nav('vehicles')
    if st.button("🛠️ Garages", use_container_width=True): nav('garages')
    st.divider()
    if st.button("➕ New Booking", type="primary", use_container_width=True): nav('new_booking')
    
    # NEW: EMAIL TESTER
    st.divider()
    st.write("**Diagnostics**")
    if st.button("📧 Test Email Config"):
        with st.spinner("Testing connection..."):
            test_res = send_confirmation_email(
                st.secrets["emails"]["smtp_user"], 
                "Admin", "TEST-REG", "System Test", "Test Garage", "Today", 0.0
            )
            if test_res:
                st.success("Test email sent to yourself!")
            else:
                st.error("Test failed. See red box above.")

# --- UI CONFIG & CSS ---
st.set_page_config(layout="wide", page_title="VBS Pro")
st.markdown("""
    <style>
    div[data-testid="metric-container"], .stMetric {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(128, 128, 128, 0.3) !important;
        padding: 20px !important;
        border-radius: 10px !important;
    }
    div[data-testid="metric-container"] label, div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: inherit !important;
    }
    .main-header { font-size: 28px; font-weight: bold; margin-bottom: 20px; }
    .section-header { font-size: 18px; font-weight: bold; color: #ff4b4b; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

if 'page' not in st.session_state: st.session_state.page = 'dashboard'
def nav(p): st.session_state.page = p

# --- SIDEBAR ---
with st.sidebar:
    st.title("🚗 VBS Pro")
    if st.button("📊 Dashboard", use_container_width=True): nav('dashboard')
    if st.button("👥 Customers", use_container_width=True): nav('customers')
    if st.button("🚗 Vehicles", use_container_width=True): nav('vehicles')
    if st.button("🛠️ Garages", use_container_width=True): nav('garages')
    st.divider()
    if st.button("➕ New Booking", type="primary", use_container_width=True): nav('new_booking')

db = SessionLocal()

# --- DASHBOARD ---
if st.session_state.page == 'dashboard':
    st.markdown('<div class="main-header">Dashboard</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Bookings", db.query(Booking).count())
    c2.metric("Customers", db.query(Customer).count())
    c3.metric("Vehicles", db.query(Vehicle).count())
    c4.metric("Garages", db.query(Garage).count())

    st.write("### Recent Bookings")
    query = db.query(Booking).options(joinedload(Booking.customer), joinedload(Booking.vehicle), joinedload(Booking.garage))
    results = query.order_by(Booking.date.desc()).all()
    data = [{"Date": b.date.strftime("%d %b %Y"), "Customer": b.customer.name, "Vehicle": b.vehicle.registration, "Garage": b.garage.name, "Job": b.job_title, "Cost": f"£{b.cost:.2f}", "Status": b.status} for b in results]
    if data: st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else: st.info("No bookings recorded yet.")

# --- MEGA FORM ---
elif st.session_state.page == 'new_booking':
    st.markdown('<div class="main-header">New Unified Booking</div>', unsafe_allow_html=True)
    existing_custs = db.query(Customer).all()
    existing_gars = db.query(Garage).all()

    with st.form("mega_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<p class="section-header">1. Customer Details</p>', unsafe_allow_html=True)
            cust_choice = st.selectbox("Existing Customer", ["-- New Customer --"] + [c.name for c in existing_custs])
            n_cust_name = st.text_input("New Name")
            n_cust_email = st.text_input("New Email")
            n_cust_phone = st.text_input("New Phone")
        with col2:
            st.markdown('<p class="section-header">2. Vehicle Details</p>', unsafe_allow_html=True)
            current_vehs = []
            if cust_choice != "-- New Customer --":
                c_obj = db.query(Customer).filter_by(name=cust_choice).first()
                current_vehs = [v.registration for v in c_obj.vehicles]
            veh_choice = st.selectbox("Existing Vehicle", ["-- New Vehicle --"] + current_vehs)
            n_veh_reg = st.text_input("New Reg").upper()
            n_veh_mod = st.text_input("New Make/Model")

        st.divider()
        col3, col4 = st.columns(2)
        with col3:
            st.markdown('<p class="section-header">3. Garage Details</p>', unsafe_allow_html=True)
            gar_choice = st.selectbox("Existing Garage", ["-- New Garage --"] + [g.name for g in existing_gars])
            n_gar_name = st.text_input("New Garage Name")
            n_gar_email = st.text_input("New Garage Email")
        with col4:
            st.markdown('<p class="section-header">4. Job Details</p>', unsafe_allow_html=True)
            job = st.text_input("Job Title")
            dt = st.date_input("Service Date")
            cost = st.number_input("Cost (£)", min_value=0.0)
        
        desc = st.text_area("Notes")
        stat = st.selectbox("Status", ["Confirmed", "In Progress", "Completed"])
        submit = st.form_submit_button("SAVE & SEND EMAIL", type="primary", use_container_width=True)

    if submit:
        try:
            # 1. SMART CHECK: CUSTOMER
            if cust_choice == "-- New Customer --":
                final_cust = db.query(Customer).filter_by(email=n_cust_email).first()
                if not final_cust:
                    final_cust = Customer(name=n_cust_name, email=n_cust_email, phone=n_cust_phone)
                    db.add(final_cust); db.flush()
            else:
                final_cust = db.query(Customer).filter_by(name=cust_choice).first()

            # 2. SMART CHECK: VEHICLE
            if veh_choice == "-- New Vehicle --":
                final_veh = db.query(Vehicle).filter_by(registration=n_veh_reg).first()
                if not final_veh:
                    final_veh = Vehicle(registration=n_veh_reg, make_model=n_veh_mod, owner=final_cust)
                    db.add(final_veh); db.flush()
            else:
                final_veh = db.query(Vehicle).filter_by(registration=veh_choice).first()

            # 3. SMART CHECK: GARAGE
            if gar_choice == "-- New Garage --":
                final_gar = db.query(Garage).filter_by(name=n_gar_name).first()
                if not final_gar:
                    final_gar = Garage(name=n_gar_name, email=n_gar_email)
                    db.add(final_gar); db.flush()
            else:
                final_gar = db.query(Garage).filter_by(name=gar_choice).first()

            # 4. SAVE BOOKING
            new_b = Booking(customer=final_cust, vehicle=final_veh, garage=final_gar, job_title=job, description=desc, date=datetime.combine(dt, datetime.min.time()), cost=cost, status=stat)
            db.add(new_b); db.commit()

            # 5. EMAIL
            with st.spinner("Processing email..."):
                if send_confirmation_email(final_cust.email, final_cust.name, final_veh.registration, job, final_gar.name, dt, cost):
                    st.success("All data saved and email sent!")
                else:
                    st.warning("Booking saved, but email failed. Check errors above.")
            st.balloons(); nav('dashboard'); st.rerun()

        except Exception as e:
            db.rollback(); st.error(f"Error: {e}")

# (Management pages)
elif st.session_state.page == 'customers':
    st.header("Manage Customers")
    for c in db.query(Customer).all():
        c1, c2 = st.columns([5,1])
        c1.write(f"**{c.name}** ({c.email})")
        if c2.button("Delete", key=f"d_c_{c.id}"): db.delete(c); db.commit(); st.rerun()

elif st.session_state.page == 'vehicles':
    st.header("Manage Vehicles")
    for v in db.query(Vehicle).all():
        c1, c2 = st.columns([5,1])
        c1.write(f"**{v.registration}** - {v.owner.name}")
        if c2.button("Delete", key=f"d_v_{v.id}"): db.delete(v); db.commit(); st.rerun()

elif st.session_state.page == 'garages':
    st.header("Manage Garages")
    for g in db.query(Garage).all():
        c1, c2 = st.columns([5,1])
        c1.write(f"**{g.name}**")
        if c2.button("Delete", key=f"d_g_{g.id}"): db.delete(g); db.commit(); st.rerun()

db.close()
