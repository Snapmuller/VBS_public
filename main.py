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

# --- EMAIL HELPER ---
def send_confirmation_email(cust_email, cust_name, veh_reg, job, garage, date_obj, cost):
    try:
        s_user = str(st.secrets["emails"]["smtp_user"]).replace('"', '').replace(' ', '').strip()
        s_pass = str(st.secrets["emails"]["smtp_pass"]).replace('"', '').replace(' ', '').strip()
        s_server = str(st.secrets["emails"]["smtp_server"]).replace('"', '').replace(' ', '').strip()
        s_port = int(str(st.secrets["emails"]["smtp_port"]).replace('"', '').replace(' ', '').strip())

        msg = MIMEMultipart()
        msg['From'] = s_user
        msg['To'] = cust_email
        msg['Subject'] = f"Booking Confirmation: {veh_reg}"
        body = f"Hello {cust_name},\n\nYour booking for {veh_reg} is confirmed.\nJob: {job}\nGarage: {garage}\nDate: {date_obj.strftime('%d %B %Y')}\nCost: £{cost:.2f}\n\nThank you!"
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(s_server, s_port, timeout=15)
        server.starttls()
        server.login(s_user, s_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email Error: {str(e)}")
        return False

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
    else: st.info("No bookings yet.")

# --- MEGA FORM: NEW BOOKING ---
elif st.session_state.page == 'new_booking':
    st.markdown('<div class="main-header">New Unified Booking Form</div>', unsafe_allow_html=True)
    st.info("Fill in the fields below. You can pick existing records OR type in new ones to create them automatically.")
    
    existing_custs = db.query(Customer).all()
    existing_gars = db.query(Garage).all()

    with st.form("mega_booking_form"):
        # ROW 1: CUSTOMER & VEHICLE
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<p class="section-header">1. Customer Details</p>', unsafe_allow_html=True)
            cust_choice = st.selectbox("Pick Existing Customer", ["-- New Customer --"] + [c.name for c in existing_custs])
            new_cust_name = st.text_input("New Customer Name (if not in list)")
            new_cust_email = st.text_input("New Customer Email")
            new_cust_phone = st.text_input("New Customer Phone")

        with col2:
            st.markdown('<p class="section-header">2. Vehicle Details</p>', unsafe_allow_html=True)
            # Find vehicles for existing customer if selected
            current_vehs = []
            if cust_choice != "-- New Customer --":
                c_obj = db.query(Customer).filter_by(name=cust_choice).first()
                current_vehs = [v.registration for v in c_obj.vehicles]
            
            veh_choice = st.selectbox("Pick Existing Vehicle", ["-- New Vehicle --"] + current_vehs)
            new_veh_reg = st.text_input("New Vehicle Reg (e.g. MC15 PGU)").upper()
            new_veh_model = st.text_input("New Vehicle Make/Model")

        st.divider()

        # ROW 2: GARAGE & BOOKING
        col3, col4 = st.columns(2)
        with col3:
            st.markdown('<p class="section-header">3. Garage Details</p>', unsafe_allow_html=True)
            gar_choice = st.selectbox("Pick Existing Garage", ["-- New Garage --"] + [g.name for g in existing_gars])
            new_gar_name = st.text_input("New Garage Name")
            new_gar_email = st.text_input("New Garage Email")

        with col4:
            st.markdown('<p class="section-header">4. Booking Details</p>', unsafe_allow_html=True)
            job = st.text_input("Job Title (e.g. Full Service)")
            dt = st.date_input("Service Date")
            cost = st.number_input("Est. Cost (£)", min_value=0.0)
            stat = st.selectbox("Initial Status", ["Confirmed", "In Progress", "Completed"])

        desc = st.text_area("Work Description / Internal Notes")

        submit = st.form_submit_button("CREATE EVERYTHING & SEND EMAIL", type="primary", use_container_width=True)

    if submit:
        try:
            # 1. Resolve Customer
            if cust_choice == "-- New Customer --":
                if not new_cust_name or not new_cust_email:
                    st.error("Please provide a name and email for the new customer."); st.stop()
                final_cust = Customer(name=new_cust_name, email=new_cust_email, phone=new_cust_phone)
                db.add(final_cust); db.flush() # Get ID without committing yet
            else:
                final_cust = db.query(Customer).filter_by(name=cust_choice).first()

            # 2. Resolve Vehicle
            if veh_choice == "-- New Vehicle --":
                if not new_veh_reg or not new_veh_model:
                    st.error("Please provide registration and model for the new vehicle."); st.stop()
                final_veh = Vehicle(registration=new_veh_reg, make_model=new_veh_model, owner=final_cust)
                db.add(final_veh); db.flush()
            else:
                final_veh = db.query(Vehicle).filter_by(registration=veh_choice).first()

            # 3. Resolve Garage
            if gar_choice == "-- New Garage --":
                if not new_gar_name or not new_gar_email:
                    st.error("Please provide garage name and email."); st.stop()
                final_gar = Garage(name=new_gar_name, email=new_gar_email)
                db.add(final_gar); db.flush()
            else:
                final_gar = db.query(Garage).filter_by(name=gar_choice).first()

            # 4. Create Booking
            new_b = Booking(
                customer=final_cust, vehicle=final_veh, garage=final_gar,
                job_title=job, description=desc, 
                date=datetime.combine(dt, datetime.min.time()),
                cost=cost, status=stat
            )
            db.add(new_b)
            db.commit()

            # 5. Email
            with st.spinner("Sending email..."):
                if send_confirmation_email(final_cust.email, final_cust.name, final_veh.registration, job, final_gar.name, dt, cost):
                    st.success("SUCCESS: Customer, Vehicle, Garage, and Booking saved. Email sent!")
                else:
                    st.warning("Booking saved, but email failed. Check secrets.")
            
            st.balloons(); nav('dashboard'); st.rerun()

        except Exception as e:
            db.rollback()
            st.error(f"Database Error: {e}")

# (Other pages like Customers, Vehicles, Garages remain as they are for managing existing data)
elif st.session_state.page == 'customers':
    st.header("Existing Customers")
    for c in db.query(Customer).all():
        col1, col2 = st.columns([4,1])
        col1.write(f"**{c.name}** - {c.email}")
        if col2.button("Delete", key=f"d_c_{c.id}"): db.delete(c); db.commit(); st.rerun()

elif st.session_state.page == 'vehicles':
    st.header("Existing Vehicles")
    for v in db.query(Vehicle).all():
        col1, col2 = st.columns([4,1])
        col1.write(f"**{v.registration}** ({v.make_model}) - Owner: {v.owner.name}")
        if col2.button("Delete", key=f"d_v_{v.id}"): db.delete(v); db.commit(); st.rerun()

elif st.session_state.page == 'garages':
    st.header("Existing Garages")
    for g in db.query(Garage).all():
        col1, col2 = st.columns([4,1])
        col1.write(f"**{g.name}** - {g.email}")
        if col2.button("Delete", key=f"d_g_{g.id}"): db.delete(g); db.commit(); st.rerun()

db.close()
