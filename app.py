# ==========================================
# SPAN Margin Calculator – Auto Load Version
# ==========================================

import streamlit as st
import pandas as pd
import numpy as np
from lxml import etree
from datetime import datetime
from pathlib import Path

# ======================================================
# PAGE CONFIG
# ======================================================

st.set_page_config(page_title="SPAN Margin Calculator", layout="wide")

# ======================================================
# STYLE
# ======================================================

st.markdown("""
<style>
.main {background:#f6f8fb;}
.header {
    background:#0b1d34;
    padding:22px 40px;
    color:white;
    font-size:26px;
    font-weight:600;
    border-radius:12px;
    margin-bottom:25px;
}
.card {
    background:white;
    padding:28px;
    border-radius:14px;
    box-shadow:0 8px 25px rgba(0,0,0,.08);
    margin-bottom:25px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header">📊 SPAN Margin Calculator</div>', unsafe_allow_html=True)

# ======================================================
# LOAD DATA FROM REPO
# ======================================================

DATA = Path("data")

index_df = pd.read_excel(next(DATA.glob("Index*")))
stock_df = pd.read_excel(next(DATA.glob("Stock*")))
combined = pd.concat([index_df, stock_df])

lot_df = pd.read_csv(next(DATA.glob("Lot*")))
elm_df = pd.read_csv(next(DATA.glob("ael*")))
date_df = pd.read_csv(next(DATA.glob("FOS*")))

tree = etree.parse(next(DATA.glob("nsccl*")))
root = tree.getroot()

# ======================================================
# BUILD STRIKE MAP
# ======================================================

span_map = {}

for pf in root.iter("oopPf"):
    symbol = pf.find("name").text
    for series in pf.findall("series"):
        expiry = series.find("pe").text
        for opt in series.findall("opt"):
            typ = opt.find("o").text
            strike = float(opt.find("k").text)
            span_map.setdefault((symbol, expiry, typ), []).append(strike)

for k in span_map:
    span_map[k] = sorted(set(span_map[k]))

def get_strikes(s,e,t):
    return span_map.get((s,e,t),[])

# ======================================================
# UI
# ======================================================

st.markdown('<div class="card">', unsafe_allow_html=True)

symbols = sorted(
    [s for s in date_df.iloc[:,2].dropna().unique()
     if not str(s).endswith("TEST")]
)

c1,c2,c3 = st.columns(3)

with c1:
    symbol = st.selectbox("Instrument", symbols)

with c2:
    deriv = st.selectbox("Type", ["Futures","Options"])

with c3:
    side = st.selectbox("Buy/Sell", ["Buy","Sell"])

expiries = sorted(date_df[date_df.iloc[:,2]==symbol].iloc[:,3].dropna().unique())

c4,c5 = st.columns(2)

with c4:
    expiry = st.selectbox("Expiry", expiries)

with c5:
    lots = st.number_input("Lots", 1, 10000, 1)

opt_type=None
strike=None

if deriv=="Options":
    c6,c7 = st.columns(2)

    with c6:
        ui_opt=st.selectbox("Option Type",["Call","Put"])
        opt_type="C" if ui_opt=="Call" else "P"

    expiry_str=datetime.strptime(expiry,"%d-%b-%Y").strftime("%Y%m%d")
    strikes=get_strikes(symbol,expiry_str,opt_type)

    with c7:
        strike=st.selectbox("Strike",strikes)

st.markdown('</div>', unsafe_allow_html=True)

# ======================================================
# CALCULATION
# ======================================================

if st.button("🚀 Calculate Margin"):

    expiry_str=datetime.strptime(expiry,"%d-%b-%Y").strftime("%Y%m%d")

    lot_size=lots
    for i in range(len(lot_df)):
        if symbol==lot_df.iloc[i,2]:
            lot_size=lot_df.iloc[i,3]*lots

    if deriv=="Futures":

        futpf=next(p for p in root.iter("futPf") if p.find("name").text==symbol)
        fut=next(f for f in futpf.findall("fut") if f.find("pe").text==expiry_str)

        a_vals=[float(a.text) for a in fut.find("ra").findall("a")]
        worst=min(a_vals) if side=="Buy" else max(a_vals)

        price=float(fut.find("p").text)

        span=abs(worst)*lot_size
        exposure=price*0.02*lot_size
        total=span+exposure

    else:

        if side=="Buy":
            span=exposure=total=0
        else:
            ooppf=next(p for p in root.iter("oopPf") if p.find("name").text==symbol)
            series=next(s for s in ooppf.findall("series") if s.find("pe").text==expiry_str)
            op=next(o for o in series.findall("opt")
                    if float(o.find("k").text)==strike and o.find("o").text==opt_type)

            a_vals=[float(a.text) for a in op.find("ra").findall("a")]
            premium=float(op.find("p").text)

            worst=abs(min(a_vals))+premium
            phy=float(next(root.iter("phy")).find("p").text)

            span=worst*lot_size
            exposure=phy*0.02*lot_size
            total=span+exposure

    r1,r2,r3=st.columns(3)
    r1.metric("SPAN Margin",f"₹ {span:,.2f}")
    r2.metric("Exposure",f"₹ {exposure:,.2f}")
    r3.metric("Total",f"₹ {total:,.2f}")
