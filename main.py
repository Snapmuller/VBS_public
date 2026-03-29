import streamlit as st
import pandas as pd
import resend
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from datetime import datetime, date

# --- 1. MUST BE THE VERY FIRST COMMAND ---
st.set_page_config(layout="wide", page_title="VBS Pro")

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

# --- RESEND API EMAIL HELPER ---
def send_confirmation_email(cust_email, cust_name, veh_reg, job, garage, date_obj, cost):
    api_key = os.getenv("RESEND_API_KEY")
    
    if not api_key:
        st.error("⚠️ RESEND_API_KEY is missing in Railway Variables.")
        return False
    
    resend.api_key = api_key

    try:
        # Note: On Resend Free Plan, 'from' must be onboarding@resend.dev
        # And you can only send to the email you signed up with.
        params = {
            "from": "VBS Pro <onboarding@resend.dev>",
            "to": [cust_email],
            "subject": f"Booking Confirmation: {veh_reg}",
            "html": f"""
                <div style="font-family: sans-serif; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #ff4b4b;">Booking Confirmed</h2>
                    <p>Hello <b>{cust_name}</b>,</p>
                    <p>Your vehicle <b>{veh_reg}</b> is booked for service.</p>
                    <hr>
                    <p><b>Job:</b> {job}</p>
                    <p><b>Garage:</b> {garage}</p>
                    <p><b>Date:</b> {date_obj}</p>
                    <p><b>Cost:</b> £{cost:.2f}</p>
                </div>
            """
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        st.error(f"❌ Email Failed: {str(e)}")
        return False

# --- CSS STYLING (FIX FOR DARK MODE WHITE BOXES) ---
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

# --- NAVIGATION ---
if 'page' not in st.session_state: st.session_state.page = 'dashboard'
def nav(p): st.session_state.page = p

db = SessionLocal()

# --- SIDEBAR ---
with st.sidebar:
    st.title("🚗 VBS Pro")
    if st.button("📊 Dashboard", use_container_width=True): nav('dashboard')
    if st.button("👥 Customers", use_container_width=True): nav('customers')
    if st.button("🚗 Vehicles", use_container_width=True): nav('vehicles')
    if st.button("🛠️ Garages", use_container_width=True): nav('garages')
    st.divider()
    if st.button("➕ New Booking", type="primary", use_container_width=True): nav('new_booking')
    
    st.divider()
    st.write("**System Status**")
    if os.getenv("RESEND_API_KEY"):
        st.success("✅ Email API Active")
        if st.button("📧 Send Test Email"):
            # Put YOUR email here to test
            admin_email = st.text_input("Test Email Address", value="")
            if admin_email:
                send_confirmation_email(admin_email, "Admin", "TEST-API", "System Test", "Cloud Garage", "Today", 0)
    else:
        st.error("❌ API Key Missing")

# --- PAGE: DASHBOARD ---
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
    else: st.info("No bookings yet.")

# --- PAGE: MEGA FORM ---
elif st.session_state.page == 'new_booking':
    st.markdown('<div class="main-header">New Booking Form</div>', unsafe_allow_html=True)
    existing_custs = db.query(Customer).all()
    existing_gars = db.query(Garage).all()

    with st.form("mega_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<p class="section-header">1. Customer</p>', unsafe_allow_html=True)
            cust_choice = st.selectbox("Existing", ["-- New Customer --"] + [c.name for c in existing_custs])
            n_name = st.text_input("New Name")
            n_email = st.text_input("New Email")
        with col2:
            st.markdown('<p class="section-header">2. Vehicle</p>', unsafe_allow_html=True)
            n_reg = st.text_input("New Reg").upper()
            n_mod = st.text_input("New Model")
        
        st.divider()
        col3, col4 = st.columns(2)
        with col3:
            st.markdown('<p class="section-header">3. Garage</p>', unsafe_allow_html=True)
            gar_choice = st.selectbox("Existing Garage", ["-- New Garage --"] + [g.name for g in existing_gars])
            n_g_name = st.text_input("Garage Name")
            n_g_email = st.text_input("Garage Email")
        with col4:
            st.markdown('<p class="section-header">4. Job</p>', unsafe_allow_html=True)
            job = st.text_input("Job Title")
            dt = st.date_input("Date")
            cost = st.number_input("Cost (£)", min_value=0.0)
        
        submit = st.form_submit_button("SAVE & SEND EMAIL", type="primary", use_container_width=True)

    if submit:
        try:
            # Resolve Customer
            if cust_choice == "-- New Customer --":
                final_cust = db.query(Customer).filter_by(email=n_email).first() or Customer(name=n_name, email=n_email)
                db.add(final_cust); db.flush()
            else:
                final_cust = db.query(Customer).filter_by(name=cust_choice).first()
            # Resolve Vehicle
            final_veh = db.query(Vehicle).filter_by(registration=n_reg).first() or Vehicle(registration=n_reg, make_model=n_mod, owner=final_cust)
            db.add(final_veh); db.flush()
            # Resolve Garage
            if gar_choice == "-- New Garage --":
                final_gar = db.query(Garage).filter_by(name=n_g_name).first() or Garage(name=n_g_name, email=n_g_email)
                db.add(final_gar); db.flush()
            else:
                final_gar = db.query(Garage).filter_by(name=gar_choice).first()
            
            # Save Booking
            new_b = Booking(customer=final_cust, vehicle=final_veh, garage=final_gar, job_title=job, date=datetime.combine(dt, datetime.min.time()), cost=cost)
            db.add(new_b); db.commit()
            
            # Send Email
            send_confirmation_email(final_cust.email, final_cust.name, final_veh.registration, job, final_gar.name, dt, cost)
            st.success("Success!"); nav('dashboard'); st.rerun()
        except Exception as e:
            db.rollback(); st.error(f"Error: {e}")

# (Management Pages)
elif st.session_state.page == 'customers':
    st.header("Customers")
    for c in db.query(Customer).all():
        st.write(f"- {c.name} ({c.email})")
elif st.session_state.page == 'vehicles':
    st.header("Vehicles")
    for v in db.query(Vehicle).all():
        st.write(f"- {v.registration} (Owner: {v.owner.name})")
elif st.session_state.page == 'garages':
    st.header("Garages")
    for g in db.query(Garage).all():
        st.write(f"- {g.name}")

db.close()
