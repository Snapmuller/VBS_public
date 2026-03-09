import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from io import StringIO

# --- DATABASE SETUP ---
Base = declarative_base()
engine = create_engine('sqlite:///vbs_database.db')
Session = sessionmaker(bind=engine)


class Customer(Base):
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    vehicles = relationship("Vehicle", back_populates="owner", cascade="all, delete-orphan")


class Vehicle(Base):
    __tablename__ = 'vehicles'
    id = Column(Integer, primary_key=True)
    registration = Column(String, unique=True, nullable=False)
    make_model = Column(String, nullable=False)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    owner = relationship("Customer", back_populates="vehicles")


class Garage(Base):
    __tablename__ = 'garages'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


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
    created_at = Column(DateTime, default=datetime.now)


Base.metadata.create_all(engine)


# --- SESSION MANAGEMENT ---
@st.cache_resource
def get_session():
    return Session()


def get_db():
    """Get database session"""
    return get_session()


# --- EMAIL HELPER FUNCTION ---
def send_confirmation_email(cust_email, cust_name, veh_reg, job, garage, date, cost):
    try:
        sender_email = st.secrets["emails"]["smtp_user"]
        sender_password = st.secrets["emails"]["smtp_pass"]
        smtp_server = st.secrets["emails"]["smtp_server"]
        smtp_port = st.secrets["emails"]["smtp_port"]

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = cust_email
        msg['Subject'] = f"Booking Confirmation: {veh_reg}"

        body = f"""
        Hello {cust_name},

        Your booking has been successfully scheduled.

        --- DETAILS ---
        Job: {job}
        Vehicle: {veh_reg}
        Garage: {garage}
        Date: {date.strftime('%d %B %Y')}
        Estimated Cost: £{cost:.2f}

        Thank you for choosing us!
        """
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email Error: {e}")
        return False


# --- NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = 'dashboard'


def nav(page_name):
    st.session_state.page = page_name


# --- SIDEBAR ---
with st.sidebar:
    st.title("🚗 VBS Pro")
    if st.button("📊 Dashboard", use_container_width=True): nav('dashboard')
    if st.button("👥 Customers", use_container_width=True): nav('customers')
    if st.button("🚗 Vehicles", use_container_width=True): nav('vehicles')
    if st.button("🛠️ Garages", use_container_width=True): nav('garages')
    st.divider()
    if st.button("➕ New Booking", type="primary", use_container_width=True): nav('new_booking')

# --- PAGE: DASHBOARD ---
if st.session_state.page == 'dashboard':
    st.title("Dashboard")
    db = get_db()

    # Stats
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Customers", db.query(Customer).count())
    c2.metric("Total Vehicles", db.query(Vehicle).count())
    c3.metric("Total Bookings", db.query(Booking).count())

    st.subheader("Recent Bookings")
    
    # Add search/filter
    col1, col2, col3 = st.columns(3)
    with col1:
        search_customer = st.text_input("Search by customer name", "")
    with col2:
        status_filter = st.selectbox("Filter by status", ["All", "Confirmed", "In Progress", "Completed", "Cancelled"])
    with col3:
        date_range = st.date_input("Filter by date range", value=[], key="date_range")

    # Query with filters
    query = db.query(Booking).order_by(Booking.id.desc())
    
    if status_filter != "All":
        query = query.filter_by(status=status_filter)
    
    bookings = query.all()
    
    if bookings:
        data = []
        for b in bookings:
            c = db.query(Customer).get(b.customer_id)
            v = db.query(Vehicle).get(b.vehicle_id)
            g = db.query(Garage).get(b.garage_id)
            
            # Apply customer name filter
            if search_customer and (not c or search_customer.lower() not in c.name.lower()):
                continue
            
            data.append({
                "ID": b.id,
                "Date": b.date.strftime("%d %b %Y"),
                "Customer": c.name if c else "Unknown",
                "Vehicle": v.registration if v else "Unknown",
                "Garage": g.name if g else "Unknown",
                "Job": b.job_title,
                "Cost": f"£{b.cost:.2f}",
                "Status": b.status
            })
        
        if data:
            st.table(pd.DataFrame(data))
        else:
            st.info("No bookings match your filters.")
    else:
        st.info("No bookings recorded yet.")

    # Export to CSV
    if bookings:
        csv_data = pd.DataFrame(data)
        csv_string = csv_data.to_csv(index=False)
        st.download_button(
            label="📥 Download Bookings as CSV",
            data=csv_string,
            file_name="bookings_export.csv",
            mime="text/csv"
        )

# --- PAGE: CUSTOMERS ---
elif st.session_state.page == 'customers':
    st.header("Manage Customers")
    db = get_db()
    
    with st.expander("➕ Add New Customer"):
        with st.form("cust_form", clear_on_submit=True):
            name = st.text_input("Full Name").strip()
            email = st.text_input("Email Address").strip()
            phone = st.text_input("Phone Number").strip()
            if st.form_submit_button("Save Customer"):
                if not name or not email:
                    st.error("Name and email are required")
                elif db.query(Customer).filter_by(email=email).first():
                    st.error("⚠️ Email already exists!")
                else:
                    try:
                        db.add(Customer(name=name, email=email, phone=phone))
                        db.commit()
                        st.success("✅ Customer added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    custs = db.query(Customer).all()
    if custs:
        cols = st.columns([2, 2, 2, 1])
        with cols[0]: st.write("**Name**")
        with cols[1]: st.write("**Email**")
        with cols[2]: st.write("**Phone**")
        with cols[3]: st.write("**Action**")
        st.divider()
        
        for c in custs:
            cols = st.columns([2, 2, 2, 1])
            with cols[0]: st.write(c.name)
            with cols[1]: st.write(c.email)
            with cols[2]: st.write(c.phone or "-")
            with cols[3]:
                if st.button("🗑️", key=f"del_cust_{c.id}", help="Delete customer"):
                    db.delete(c)
                    db.commit()
                    st.success("Customer deleted")
                    st.rerun()

# --- PAGE: VEHICLES ---
elif st.session_state.page == 'vehicles':
    st.header("Manage Vehicles")
    db = get_db()
    custs = db.query(Customer).all()
    
    if not custs:
        st.warning("Please add a customer first.")
    else:
        with st.expander("➕ Add New Vehicle"):
            with st.form("veh_form", clear_on_submit=True):
                reg = st.text_input("Registration").strip().upper()
                model = st.text_input("Make/Model").strip()
                owner_id = st.selectbox("Owner", [c.id for c in custs],
                                        format_func=lambda x: db.query(Customer).get(x).name)
                if st.form_submit_button("Save Vehicle"):
                    if not reg or not model:
                        st.error("All fields are required")
                    elif db.query(Vehicle).filter_by(registration=reg).first():
                        st.error("⚠️ Registration already exists!")
                    else:
                        try:
                            db.add(Vehicle(registration=reg, make_model=model, customer_id=owner_id))
                            db.commit()
                            st.success("✅ Vehicle registered!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        vehs = db.query(Vehicle).all()
        if vehs:
            cols = st.columns([1.5, 2, 2, 1])
            with cols[0]: st.write("**Reg**")
            with cols[1]: st.write("**Model**")
            with cols[2]: st.write("**Owner**")
            with cols[3]: st.write("**Action**")
            st.divider()
            
            for v in vehs:
                cols = st.columns([1.5, 2, 2, 1])
                with cols[0]: st.write(v.registration)
                with cols[1]: st.write(v.make_model)
                with cols[2]: st.write(v.owner.name)
                with cols[3]:
                    if st.button("🗑️", key=f"del_veh_{v.id}", help="Delete vehicle"):
                        db.delete(v)
                        db.commit()
                        st.success("Vehicle deleted")
                        st.rerun()

# --- PAGE: GARAGES ---
elif st.session_state.page == 'garages':
    st.header("Manage Garages")
    db = get_db()
    
    with st.expander("➕ Add New Garage"):
        with st.form("gar_form", clear_on_submit=True):
            g_name = st.text_input("Garage Name").strip()
            g_email = st.text_input("Garage Email").strip()
            if st.form_submit_button("Save Garage"):
                if not g_name or not g_email:
                    st.error("All fields are required")
                elif db.query(Garage).filter_by(name=g_name).first():
                    st.error("⚠️ Garage name already exists!")
                else:
                    try:
                        db.add(Garage(name=g_name, email=g_email))
                        db.commit()
                        st.success("✅ Garage added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    garages = db.query(Garage).all()
    if garages:
        cols = st.columns([2, 3, 1])
        with cols[0]: st.write("**Name**")
        with cols[1]: st.write("**Email**")
        with cols[2]: st.write("**Action**")
        st.divider()
        
        for g in garages:
            cols = st.columns([2, 3, 1])
            with cols[0]: st.write(g.name)
            with cols[1]: st.write(g.email)
            with cols[2]:
                if st.button("🗑️", key=f"del_gar_{g.id}", help="Delete garage"):
                    db.delete(g)
                    db.commit()
                    st.success("Garage deleted")
                    st.rerun()

# --- PAGE: NEW BOOKING ---
elif st.session_state.page == 'new_booking':
    st.header("Create New Booking")
    db = get_db()

    customers = db.query(Customer).all()
    garages = db.query(Garage).all()

    if not customers or not garages:
        st.error("Setup required: Ensure you have at least one Customer and one Garage.")
    else:
        with st.form("booking_form"):
            col1, col2 = st.columns(2)
            with col1:
                sel_cust = st.selectbox("Customer", customers, format_func=lambda x: x.name)
                cust_vehs = db.query(Vehicle).filter_by(customer_id=sel_cust.id).all()
                if not cust_vehs:
                    st.warning("This customer has no vehicles!")
                    sel_veh = None
                else:
                    sel_veh = st.selectbox("Vehicle", cust_vehs, format_func=lambda x: f"{x.registration} ({x.make_model})")
                sel_gar = st.selectbox("Garage", garages, format_func=lambda x: x.name)

            with col2:
                job_title = st.text_input("Job Title", placeholder="e.g. Full Service").strip()
                job_date = st.date_input("Date")
                job_cost = st.number_input("Cost (£)", min_value=0.0, step=10.0)

            job_desc = st.text_area("Job Description").strip()
            job_status = st.selectbox("Status", ["Confirmed", "In Progress", "Completed", "Cancelled"])

            if st.form_submit_button("Confirm Booking & Send Email"):
                if not job_title:
                    st.error("Job title is required")
                elif not sel_veh:
                    st.error("This customer has no vehicles!")
                else:
                    # 1. Save to Database
                    new_b = Booking(
                        customer_id=sel_cust.id,
                        vehicle_id=sel_veh.id,
                        garage_id=sel_gar.id,
                        job_title=job_title,
                        description=job_desc,
                        date=datetime.combine(job_date, datetime.min.time()),
                        cost=job_cost,
                        status=job_status
                    )
                    db.add(new_b)
                    db.commit()

                    # 2. Send Email
                    with st.spinner("Sending confirmation to customer..."):
                        success = send_confirmation_email(
                            cust_email=sel_cust.email,
                            cust_name=sel_cust.name,
                            veh_reg=sel_veh.registration,
                            job=job_title,
                            garage=sel_gar.name,
                            date=job_date,
                            cost=job_cost
                        )

                    if success:
                        st.success(f"✅ Booking saved and email sent to {sel_cust.email}")
                        st.balloons()
                    else:
                        st.warning("Booking saved, but email failed. Check your secrets.")