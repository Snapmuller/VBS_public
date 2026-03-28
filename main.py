import streamlit as st
import pandas as pd
import smtplib
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Text, or_
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

def get_db():
    return SessionLocal()

# --- EMAIL HELPER ---
def send_confirmation_email(cust_email, cust_name, veh_reg, job, garage, date_obj, cost):
    try:
        # Fetching secrets and ensuring no accidental quotes or spaces
        s_user = str(st.secrets["emails"]["smtp_user"]).strip().replace('"', '')
        s_pass = str(st.secrets["emails"]["smtp_pass"]).strip().replace('"', '')
        s_server = str(st.secrets["emails"]["smtp_server"]).strip().replace('"', '')
        s_port = int(str(st.secrets["emails"]["smtp_port"]).strip().replace('"', ''))

        msg = MIMEMultipart()
        msg['From'] = s_user
        msg['To'] = cust_email
        msg['Subject'] = f"Booking Confirmation: {veh_reg}"

        body = f"""Hello {cust_name},

Your booking for {veh_reg} is confirmed.

Job: {job}
Garage: {garage}
Date: {date_obj.strftime('%d %B %Y')}
Estimated Cost: £{cost:.2f}

Thank you!"""
        
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(s_server, s_port)
        server.starttls()
        server.login(s_user, s_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email Error Trace: {e}")
        return False

# --- UI CONFIG & CSS FIX ---
st.set_page_config(layout="wide", page_title="VBS Pro")
st.markdown("""
    <style>
    /* Fixed: Removed white background to support Dark Mode */
    [data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 15px;
        border-radius: 10px;
    }
    .main-header { font-size: 28px; font-weight: bold; margin-bottom: 20px; }
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

# --- DASHBOARD ---
if st.session_state.page == 'dashboard':
    st.markdown('<div class="main-header">Dashboard</div>', unsafe_allow_html=True)
    db = get_db()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Bookings", db.query(Booking).count())
    c2.metric("Customers", db.query(Customer).count())
    c3.metric("Vehicles", db.query(Vehicle).count())
    c4.metric("Garages", db.query(Garage).count())

    st.write("### Recent Bookings")
    col_a, col_b, col_c = st.columns(3)
    with col_a: search = st.text_input("🔍 Search Customer/Reg")
    with col_b: status = st.selectbox("Status", ["All", "Confirmed", "In Progress", "Completed", "Cancelled"])
    with col_c: d_range = st.date_input("Date Range", value=[date(2023, 1, 1), date(2026, 12, 31)])

    query = db.query(Booking).options(joinedload(Booking.customer), joinedload(Booking.vehicle), joinedload(Booking.garage))
    if status != "All": query = query.filter(Booking.status == status)
    if len(d_range) == 2: query = query.filter(Booking.date.between(d_range[0], d_range[1]))

    results = query.order_by(Booking.date.desc()).all()
    data = []
    for b in results:
        if not search or search.lower() in b.customer.name.lower() or search.lower() in b.vehicle.registration.lower():
            data.append({
                "Date": b.date.strftime("%d %b %Y"),
                "Customer": b.customer.name,
                "Vehicle": b.vehicle.registration,
                "Garage": b.garage.name,
                "Job": b.job_title,
                "Cost": f"£{b.cost:.2f}",
                "Status": b.status
            })

    if data: st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else: st.info("No bookings match filters.")
    db.close()

# --- CUSTOMERS ---
elif st.session_state.page == 'customers':
    st.header("Manage Customers")
    db = get_db()
    with st.expander("➕ Add New Customer"):
        with st.form("c_form", clear_on_submit=True):
            name = st.text_input("Full Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            if st.form_submit_button("Save"):
                if db.query(Customer).filter_by(email=email).first(): st.error("Email exists")
                else:
                    db.add(Customer(name=name, email=email, phone=phone))
                    db.commit(); st.success("Added!"); st.rerun()

    for c in db.query(Customer).all():
        col1, col2, col3 = st.columns([3, 3, 1])
        col1.write(f"**{c.name}** ({c.email})")
        col2.write(f"📞 {c.phone}")
        if col3.button("🗑️", key=f"del_c_{c.id}"):
            db.delete(c); db.commit(); st.rerun()
    db.close()

# --- VEHICLES ---
elif st.session_state.page == 'vehicles':
    st.header("Manage Vehicles")
    db = get_db()
    custs = db.query(Customer).all()
    if not custs: st.warning("Add a customer first")
    else:
        with st.expander("➕ Add New Vehicle"):
            with st.form("v_form", clear_on_submit=True):
                reg = st.text_input("Registration").upper()
                mod = st.text_input("Make/Model")
                owner_id = st.selectbox("Owner", [c.id for c in custs], format_func=lambda x: db.query(Customer).get(x).name)
                if st.form_submit_button("Save"):
                    db.add(Vehicle(registration=reg, make_model=mod, customer_id=owner_id))
                    db.commit(); st.success("Added!"); st.rerun()

    for v in db.query(Vehicle).options(joinedload(Vehicle.owner)).all():
        c1, c2, c3 = st.columns([2, 2, 1])
        c1.write(f"**{v.registration}** - {v.make_model}")
        c2.write(f"👤 {v.owner.name}")
        if c3.button("🗑️", key=f"del_v_{v.id}"):
            db.delete(v); db.commit(); st.rerun()
    db.close()

# --- GARAGES ---
elif st.session_state.page == 'garages':
    st.header("Manage Garages")
    db = get_db()
    with st.expander("➕ Add New Garage"):
        with st.form("g_form", clear_on_submit=True):
            name = st.text_input("Name")
            email = st.text_input("Email")
            if st.form_submit_button("Save"):
                db.add(Garage(name=name, email=email))
                db.commit(); st.success("Added!"); st.rerun()

    for g in db.query(Garage).all():
        c1, c2, c3 = st.columns([2, 2, 1])
        c1.write(f"**{g.name}**")
        c2.write(g.email)
        if c3.button("🗑️", key=f"del_g_{g.id}"):
            db.delete(g); db.commit(); st.rerun()
    db.close()

# --- NEW BOOKING ---
elif st.session_state.page == 'new_booking':
    st.header("New Booking")
    db = get_db()
    custs = db.query(Customer).all()
    gars = db.query(Garage).all()

    if not custs or not gars: st.error("Add Customers and Garages first!")
    else:
        with st.form("b_form"):
            col1, col2 = st.columns(2)
            with col1:
                sel_cust = st.selectbox("Customer", custs, format_func=lambda x: x.name)
                vehs = db.query(Vehicle).filter_by(customer_id=sel_cust.id).all()
                sel_veh = st.selectbox("Vehicle", vehs, format_func=lambda x: f"{x.registration} ({x.make_model})") if vehs else None
                sel_gar = st.selectbox("Garage", gars, format_func=lambda x: x.name)
            with col2:
                job = st.text_input("Job Title")
                dt = st.date_input("Date")
                cost = st.number_input("Cost (£)", min_value=0.0)

            desc = st.text_area("Description")
            stat = st.selectbox("Status", ["Confirmed", "In Progress", "Completed", "Cancelled"])

            if st.form_submit_button("Create & Send Email"):
                if not sel_veh: st.error("Customer has no vehicles!")
                else:
                    new_b = Booking(customer_id=sel_cust.id, vehicle_id=sel_veh.id, garage_id=sel_gar.id,
                                    job_title=job, description=desc, date=datetime.combine(dt, datetime.min.time()),
                                    cost=cost, status=stat)
                    db.add(new_b); db.commit()
                    with st.spinner("Sending email..."):
                        if send_confirmation_email(sel_cust.email, sel_cust.name, sel_veh.registration, job, sel_gar.name, dt, cost):
                            st.success("Booking saved and email sent!")
                        else: st.warning("Booking saved, but email failed. Check Railway variables.")
                    nav('dashboard'); st.rerun()
    db.close()
