"""
Financing Portfolio Dashboard (Streamlit)

Jalankan:
    pip install -r requirements.txt
    streamlit run dashboard.py

File data (Data_Dummy_Finance_5000.xlsx) taruh satu folder dengan dashboard.py.
Kalau file tidak ditemukan, dashboard menyediakan tombol upload di sidebar.
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------------ config
st.set_page_config(
    page_title="Financing Portfolio Dashboard",
    page_icon="📊",
    layout="wide",
)

# angka KPI sedikit diperkecil supaya tidak terpotong ("Rp 1,1...")
st.markdown(
    "<style>[data-testid='stMetricValue']{font-size:1.65rem;}</style>",
    unsafe_allow_html=True,
)

DATA_FILE = Path(__file__).parent / "Data_Dummy_Finance_5000.xlsx"

# Palet kategorikal (urutan tetap) + warna status
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
CRITICAL, MUTED = "#d03b3b", "#898781"
SEGMEN_COLOR = {"Retail": BLUE, "UMKM": ORANGE, "Corporate": AQUA}

AGING_ORDER = ["Current", "1-30", "31-60", "61-90", ">90", "Write Off"]
AGING_COLOR = {
    "Current": BLUE, "1-30": BLUE, "31-60": BLUE, "61-90": BLUE,
    ">90": CRITICAL, "Write Off": MUTED,
}

# metrik yang bisa dipilih di beberapa chart: label -> (kolom, fungsi, pembagi)
METRICS = {
    "AF (Rp miliar)": ("AF", "sum", 1e9),
    "AR (Rp miliar)": ("AR", "sum", 1e9),
    "Jumlah Kontrak": ("No_Kontrak", "nunique", 1),
}


# ------------------------------------------------------------------ helpers
def idn(v, d=1):
    """Format angka gaya Indonesia: 1.234,5"""
    s = f"{v:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def rp(v):
    """Format rupiah ringkas: Rp 12,3 M (miliar) / Rp 4,5 Jt."""
    a = abs(v)
    if a >= 1e12:
        return f"Rp {idn(v / 1e12, 2)} T"
    if a >= 1e9:
        return f"Rp {idn(v / 1e9, 2)} M"
    if a >= 1e6:
        return f"Rp {idn(v / 1e6, 1)} Jt"
    return f"Rp {idn(v, 0)}"


def pct(v, d=2):
    return f"{idn(v * 100, d)}%"


def agg_metric(df, by, label):
    col, fn, div = METRICS[label]
    out = df.groupby(by, observed=True)[col].agg(fn).div(div).rename("Nilai")
    return out.reset_index()


def npl_by(df, by):
    g = (
        df.groupby(by, observed=True)
        .agg(
            Total_AR=("AR", "sum"),
            AR_NPL=("AR_NPL", "sum"),
            AR_PAR30=("AR_PAR30", "sum"),
            Kontrak=("No_Kontrak", "nunique"),
            Total_AF=("AF", "sum"),
        )
        .reset_index()
    )
    ar = g["Total_AR"].replace(0, np.nan)
    g["NPL_Ratio"] = (g["AR_NPL"] / ar).fillna(0)
    g["PAR30_Ratio"] = (g["AR_PAR30"] / ar).fillna(0)
    return g


def style(fig, height=340, grid="y"):
    """Gaya dasar semua chart: transparan (ikut tema Streamlit), grid tipis."""
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=10, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        bargap=0.35,
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", size=12),
    )
    try:  # sudut bar membulat: hanya ada di plotly >= 6.1
        fig.update_layout(barcornerradius=4)
    except ValueError:
        pass
    grid_c = "rgba(137,135,129,0.25)"
    fig.update_xaxes(showgrid="x" in grid, gridcolor=grid_c, zeroline=False,
                     linecolor=grid_c, ticks="")
    fig.update_yaxes(showgrid="y" in grid, gridcolor=grid_c, zeroline=False,
                     linecolor=grid_c, ticks="")
    return fig


def _stretch():
    """Argumen lebar penuh: Streamlit >= 1.50 pakai width='stretch', versi lama use_container_width."""
    try:
        from packaging.version import Version
        if Version(st.__version__) >= Version("1.50"):
            return {"width": "stretch"}
    except Exception:
        pass
    return {"use_container_width": True}


def show(fig):
    st.plotly_chart(fig, config={"displayModeBar": False}, **_stretch())


def table(d, **kw):
    st.dataframe(d, **_stretch(), **kw)


def kpi(col, label, value, help=None):
    """Kartu KPI dengan border (st.metric(border=True) hanya ada di versi baru)."""
    with col:
        with st.container(border=True):
            st.metric(label, value, help=help)


def bar_h(d, y, x, fmt, color=BLUE, height=340, xtitle=None, vline=None):
    """Bar horizontal, terbesar di atas, label nilai di ujung bar."""
    d = d.sort_values(x, ascending=True)
    fig = go.Figure(
        go.Bar(
            x=d[x], y=d[y].astype(str), orientation="h",
            marker_color=color,
            text=d[x].map(fmt), textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>%{text}<extra></extra>",
        )
    )
    style(fig, height, grid="x")
    fig.update_layout(margin=dict(l=0, r=50, t=10, b=0))
    fig.update_xaxes(title=xtitle)
    if vline is not None:
        fig.update_layout(margin=dict(l=0, r=50, t=35, b=0))
        fig.add_vline(x=vline[0], line_dash="dash", line_color=MUTED, line_width=1.5,
                      annotation_text=vline[1], annotation_position="top",
                      annotation_font_size=11)
    return fig


def bar_v(x, y, texts, colors=BLUE, height=340, ytitle=None, tickformat=None):
    fig = go.Figure(
        go.Bar(
            x=x, y=y, marker_color=colors,
            text=texts, textposition="outside", cliponaxis=False,
            hovertemplate="%{x}<br>%{text}<extra></extra>",
        )
    )
    style(fig, height, grid="y")
    fig.update_yaxes(title=ytitle)
    if tickformat:
        fig.update_xaxes(tickformat=tickformat)
    return fig


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner="Memuat data...")
def load_data(src) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(src) if isinstance(src, bytes) else src)

    # tanggal
    for c in [c for c in df.columns if c.startswith("Tanggal_")]:
        df[c] = pd.to_datetime(df[c], errors="coerce")

    df["Bulan_Kontrak"] = df["Tanggal_Kontrak"].dt.to_period("M").dt.to_timestamp()
    df["Tahun_Kontrak"] = df["Tanggal_Kontrak"].dt.year
    df["Kuartal_Kontrak"] = df["Tanggal_Kontrak"].dt.to_period("Q").astype(str)

    # DPD = posisi data - jatuh tempo angsuran berikutnya (minimal 0)
    df["DPD"] = (df["Tanggal_Data"] - df["Tanggal_Jatuh_Tempo_Berikutnya"]).dt.days.clip(lower=0)

    # bucket: Lunas & Write Off tidak punya jatuh tempo berikutnya, jadi dipisah
    conds = [
        df["Status_Kontrak"].eq("Lunas"),
        df["Status_Kontrak"].eq("Write Off"),
        df["DPD"].eq(0),
        df["DPD"].between(1, 30),
        df["DPD"].between(31, 60),
        df["DPD"].between(61, 90),
        df["DPD"].gt(90),
    ]
    labels = ["Lunas", "Write Off", "Current", "1-30", "31-60", "61-90", ">90"]
    df["Aging_Bucket"] = np.select(conds, labels, default="Lainnya")

    # AR yang masuk NPL (DPD > 90) dan PAR30 (DPD > 30)
    df["AR_NPL"] = df["AR"].where(df["DPD"] > 90, 0)
    df["AR_PAR30"] = df["AR"].where(df["DPD"] > 30, 0)

    # LTV = AF / Harga aset
    df["LTV"] = df["AF"] / df["Harga_Aset"].replace(0, np.nan)
    df["LTV_Bucket"] = pd.cut(
        df["LTV"], bins=[0, 0.5, 0.7, 0.8, 10],
        labels=["<50%", "50-70%", "70-80%", ">80%"],
    )
    return df


def get_data() -> pd.DataFrame:
    if DATA_FILE.exists():
        return load_data(str(DATA_FILE))
    up = st.sidebar.file_uploader("Upload Data_Dummy_Finance_5000.xlsx", type=["xlsx"])
    if up is None:
        st.info("File data tidak ditemukan di folder dashboard. Upload file Excel lewat sidebar.")
        st.stop()
    return load_data(up.getvalue())


data = get_data()
cutoff = data["Tanggal_Data"].max()

# ------------------------------------------------------------------ sidebar filters
st.sidebar.header("Filter")
st.sidebar.caption("Semua filter berlaku untuk seluruh visual.")

min_d = data["Tanggal_Kontrak"].min().date()
max_d = data["Tanggal_Kontrak"].max().date()
date_range = st.sidebar.date_input(
    "Periode Kontrak", value=(min_d, max_d), min_value=min_d, max_value=max_d
)
if len(date_range) != 2:
    st.info("Pilih tanggal akhir periode di sidebar.")
    st.stop()


def multi(label, col):
    opts = sorted(data[col].dropna().unique().tolist())
    return st.sidebar.multiselect(label, opts, default=opts)


sel_cabang = multi("Cabang", "Cabang")
sel_produk = multi("Produk", "Produk")
sel_segmen = multi("Segmen", "Segmen")
sel_channel = multi("Channel", "Channel")
sel_status = multi("Status Kontrak", "Status_Kontrak")

mask = (
    data["Tanggal_Kontrak"].dt.date.between(date_range[0], date_range[1])
    & data["Cabang"].isin(sel_cabang)
    & data["Produk"].isin(sel_produk)
    & data["Segmen"].isin(sel_segmen)
    & data["Channel"].isin(sel_channel)
    & data["Status_Kontrak"].isin(sel_status)
)
df = data[mask]

# ------------------------------------------------------------------ header + KPI
st.title("Financing Portfolio Dashboard")
st.caption(
    f"Posisi data per {cutoff:%d %b %Y} · {len(df):,} dari {len(data):,} kontrak sesuai filter · "
    "M = miliar, Jt = juta, T = triliun"
)

if df.empty:
    st.warning("Tidak ada data untuk kombinasi filter ini. Longgarkan filter di sidebar.")
    st.stop()

tot_af = df["AF"].sum()
tot_ar = df["AR"].sum()
n_kontrak = df["No_Kontrak"].nunique()
npl = df["AR_NPL"].sum() / tot_ar if tot_ar else 0
par30 = df["AR_PAR30"].sum() / tot_ar if tot_ar else 0

k = st.columns(6)
k[0].metric("Total AF (Rp)", rp(tot_af).replace("Rp ", ""), border=True,
            help="Amount Financed: total pembiayaan yang dicairkan")
k[1].metric("AR / Outstanding (Rp)", rp(tot_ar).replace("Rp ", ""), border=True,
            help="Sisa pokok yang belum dibayar")
k[2].metric("Jumlah Kontrak", f"{n_kontrak:,}".replace(",", "."), border=True)
k[3].metric("Ticket Size (Rp)", rp(tot_af / n_kontrak).replace("Rp ", ""), border=True,
            help="Rata-rata AF per kontrak")
k[4].metric("NPL Ratio", pct(npl), border=True, help="AR dengan DPD > 90 hari / total AR")
k[5].metric("PAR > 30", pct(par30), border=True, help="AR dengan DPD > 30 hari / total AR")

tab_ring, tab_kredit, tab_sales, tab_data = st.tabs(
    ["Ringkasan", "Kualitas Kredit", "Sales & Channel", "Data"]
)

# ================================================================== TAB 1
with tab_ring:
    c1, c2 = st.columns([2, 1])

    with c1:
        st.markdown("##### Tren per bulan kontrak")
        m_trend = st.radio("Metrik", ["AF (Rp miliar)", "Jumlah Kontrak"],
                           horizontal=True, key="m_trend", label_visibility="collapsed")
        t = agg_metric(df, "Bulan_Kontrak", m_trend)
        dec = 1 if m_trend.startswith("AF") else 0
        fig = bar_v(t["Bulan_Kontrak"], t["Nilai"], t["Nilai"].map(lambda v: idn(v, dec)),
                    height=330, ytitle=m_trend, tickformat="%b %y")
        fig.update_traces(textposition="none")  # 40+ bar: label hanya lewat hover
        show(fig)

    with c2:
        st.markdown("##### Komposisi segmen (by AF)")
        seg = df.groupby("Segmen")["AF"].sum().reset_index()
        fig = go.Figure(
            go.Pie(
                labels=seg["Segmen"], values=seg["AF"], hole=0.58,
                marker=dict(colors=[SEGMEN_COLOR.get(s, MUTED) for s in seg["Segmen"]],
                            line=dict(color="rgba(0,0,0,0)", width=2)),
                textinfo="percent", sort=False,
                hovertemplate="%{label}<br>%{percent}<extra></extra>",
            )
        )
        style(fig, 330)
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.05))
        show(fig)

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("##### Performa per cabang")
        m_cab = st.radio("Metrik", list(METRICS), horizontal=True, key="m_cab",
                         label_visibility="collapsed")
        d = agg_metric(df, "Cabang", m_cab)
        dec = 0 if m_cab == "Jumlah Kontrak" else 1
        show(bar_h(d, "Cabang", "Nilai", lambda v: idn(v, dec), height=520))

    with c4:
        st.markdown("##### Produk (by AF, Rp miliar)")
        d = agg_metric(df, "Produk", "AF (Rp miliar)")
        show(bar_h(d, "Produk", "Nilai", lambda v: idn(v, 1), height=250))
        st.markdown("##### Region (by AF, Rp miliar)")
        d = agg_metric(df, "Region", "AF (Rp miliar)")
        show(bar_h(d, "Region", "Nilai", lambda v: idn(v, 1), height=250))

# ================================================================== TAB 2
with tab_kredit:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### Aging bucket (AR, Rp miliar)")
        ag = (
            df[df["Aging_Bucket"].isin(AGING_ORDER)]
            .groupby("Aging_Bucket")
            .agg(AR=("AR", "sum"), Kontrak=("No_Kontrak", "nunique"))
            .reindex(AGING_ORDER)
            .fillna(0)
            .reset_index()
        )
        ag["AR_M"] = ag["AR"] / 1e9
        fig = bar_v(ag["Aging_Bucket"], ag["AR_M"], ag["AR_M"].map(lambda v: idn(v, 1)),
                    colors=[AGING_COLOR[b] for b in ag["Aging_Bucket"]], height=340)
        fig.update_traces(customdata=ag["Kontrak"],
                          hovertemplate="%{x}<br>AR Rp %{text} M<br>%{customdata} kontrak<extra></extra>")
        show(fig)
        st.caption("Merah = NPL (DPD > 90 hari). Abu-abu = Write Off. Kontrak Lunas tidak punya AR.")

    with c2:
        st.markdown("##### NPL ratio per cabang")
        g = npl_by(df, "Cabang")
        g["v"] = g["NPL_Ratio"] * 100
        show(bar_h(g, "Cabang", "v", lambda v: f"{idn(v, 1)}%", color=CRITICAL, height=520,
                   xtitle="% dari AR cabang", vline=(npl * 100, f"Portofolio {pct(npl, 1)}")))

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("##### NPL ratio per produk")
        g = npl_by(df, "Produk")
        g["v"] = g["NPL_Ratio"] * 100
        show(bar_h(g, "Produk", "v", lambda v: f"{idn(v, 1)}%", color=CRITICAL, height=280))

        st.markdown("##### NPL ratio per LTV bucket")
        g = npl_by(df, "LTV_Bucket")
        g["v"] = g["NPL_Ratio"] * 100
        fig = bar_v(g["LTV_Bucket"].astype(str), g["v"], g["v"].map(lambda v: f"{idn(v, 1)}%"),
                    colors=CRITICAL, height=280)
        show(fig)

    with c4:
        st.markdown("##### NPL ratio per kuartal kontrak (vintage)")
        g = npl_by(df, "Kuartal_Kontrak").sort_values("Kuartal_Kontrak")
        g["v"] = g["NPL_Ratio"] * 100
        fig = go.Figure(
            go.Scatter(
                x=g["Kuartal_Kontrak"], y=g["v"], mode="lines+markers",
                line=dict(color=CRITICAL, width=2), marker=dict(size=8, color=CRITICAL,
                                                                 line=dict(color="rgba(0,0,0,0)", width=0)),
                hovertemplate="%{x}<br>NPL %{y:.2f}%<extra></extra>",
            )
        )
        style(fig, 280, grid="y")
        fig.update_yaxes(title="% dari AR")
        show(fig)

        st.markdown("##### Status kontrak (jumlah)")
        g = df.groupby("Status_Kontrak")["No_Kontrak"].nunique().reset_index()
        show(bar_h(g, "Status_Kontrak", "No_Kontrak", lambda v: f"{int(v):,}".replace(",", "."),
                   height=280))

# ================================================================== TAB 3
with tab_sales:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### Top 10 AE")
        m_ae = st.radio("Metrik", ["AF (Rp miliar)", "Jumlah Kontrak"], horizontal=True,
                        key="m_ae", label_visibility="collapsed")
        d = agg_metric(df, "AE_Sales", m_ae).nlargest(10, "Nilai")
        dec = 1 if m_ae.startswith("AF") else 0
        show(bar_h(d, "AE_Sales", "Nilai", lambda v: idn(v, dec), height=400))

    with c2:
        st.markdown("##### Top 5 Dealer")
        m_dl = st.radio("Metrik", ["AF (Rp miliar)", "Jumlah Kontrak"], horizontal=True,
                        key="m_dl", label_visibility="collapsed")
        d = agg_metric(df[df["Dealer"].notna()], "Dealer", m_dl).nlargest(5, "Nilai")
        dec = 1 if m_dl.startswith("AF") else 0
        if d.empty:
            st.info("Tidak ada kontrak berchannel Dealer pada filter ini.")
        else:
            show(bar_h(d, "Dealer", "Nilai", lambda v: idn(v, dec), height=400))

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("##### Channel (by AF, Rp miliar)")
        d = agg_metric(df, "Channel", "AF (Rp miliar)")
        show(bar_h(d, "Channel", "Nilai", lambda v: idn(v, 1), height=320))
    with c4:
        st.markdown("##### Kualitas per channel (NPL ratio)")
        g = npl_by(df, "Channel")
        g["v"] = g["NPL_Ratio"] * 100
        show(bar_h(g, "Channel", "v", lambda v: f"{idn(v, 1)}%", color=CRITICAL, height=320))

    st.markdown("##### Detail per AE")
    ae = npl_by(df, ["ID_AE", "AE_Sales", "Cabang"])
    ae_tbl = pd.DataFrame(
        {
            "ID AE": ae["ID_AE"],
            "AE Sales": ae["AE_Sales"],
            "Cabang": ae["Cabang"],
            "Kontrak": ae["Kontrak"],
            "AF (Rp miliar)": ae["Total_AF"] / 1e9,
            "AR (Rp miliar)": ae["Total_AR"] / 1e9,
            "NPL (%)": ae["NPL_Ratio"] * 100,
        }
    ).sort_values("AF (Rp miliar)", ascending=False)
    st.dataframe(
        ae_tbl, hide_index=True, width="stretch",
        column_config={
            "AF (Rp miliar)": st.column_config.NumberColumn(format="%.2f"),
            "AR (Rp miliar)": st.column_config.NumberColumn(format="%.2f"),
            "NPL (%)": st.column_config.NumberColumn(format="%.2f"),
        },
    )

# ================================================================== TAB 4
with tab_data:
    st.markdown("##### KPI per cabang")
    cb = npl_by(df, ["Cabang", "Region"])
    cb_tbl = pd.DataFrame(
        {
            "Cabang": cb["Cabang"],
            "Region": cb["Region"],
            "Kontrak": cb["Kontrak"],
            "AF (Rp miliar)": cb["Total_AF"] / 1e9,
            "AR (Rp miliar)": cb["Total_AR"] / 1e9,
            "Ticket Size (Rp juta)": cb["Total_AF"] / cb["Kontrak"].replace(0, np.nan) / 1e6,
            "NPL (%)": cb["NPL_Ratio"] * 100,
            "PAR>30 (%)": cb["PAR30_Ratio"] * 100,
        }
    ).sort_values("AF (Rp miliar)", ascending=False)
    st.dataframe(
        cb_tbl, hide_index=True, width="stretch",
        column_config={
            c: st.column_config.NumberColumn(format="%.2f")
            for c in ["AF (Rp miliar)", "AR (Rp miliar)", "Ticket Size (Rp juta)", "NPL (%)", "PAR>30 (%)"]
        },
    )

    st.markdown("##### Data kontrak (terfilter)")
    st.download_button(
        "Unduh data terfilter (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        file_name="data_kontrak_terfilter.csv",
        mime="text/csv",
    )
    st.dataframe(df.drop(columns=["Bulan_Kontrak", "Kuartal_Kontrak"]), width="stretch", height=420)
