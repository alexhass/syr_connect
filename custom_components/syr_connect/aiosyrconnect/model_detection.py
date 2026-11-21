"""Device model signatures of the SYR devices and their detection.

A signature tells how a model is detected (device kind of the cloud, status checks)
and how it is addressed (local path of the JSON API, alarm commands).
`detect_model_signature()` selects the signature of a device from the cloud device
kind and its status. The caller may pass signatures of its own that extend
`SyrConnectModelSignature`, in the order of `MODEL_SIGNATURES`.
"""

from collections.abc import Sequence
import logging

from .models import SyrConnectModelSignature

_LOGGER = logging.getLogger(__name__)

# Signatures of the known models, derived from fixtures and the dkv table in
# docs/syrconnect-protocol.md. Each signature may include explicit checks (exact
# `getCNA` value, serial number or version patterns). The order matters: the status
# checks return the first signature that matches.
MODEL_SIGNATURES: tuple[SyrConnectModelSignature, ...] = (
    # ── Safe-T+ (dk=1) ──────────────────────────────────────────────────────────
    SyrConnectModelSignature(
        base_path=None,
        dk=1,
        dkv=6,
        name="safetplus",
        ver_prefix="Safe-T+",
    ),
    # ── Safe-T Master / Slave / Communication module (dk=2, 3, 5) ──────────────────
    SyrConnectModelSignature(
        base_path=None,
        dk=2,
        dkv=2,
        name="safetmaster",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=3,
        dkv=3,
        name="safetslave",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=3,
        dkv=4,
        name="safetslaveinwall",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=5,
        dkv=12,
        name="safetcomm",
        # TODO: Untested model.
    ),
    # ── Safe-T Hygiene module (dk=4) ─────────────────────────────────────────────
    SyrConnectModelSignature(
        base_path=None,
        dk=4,
        dkv=5,
        name="safethygienemodulecold",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=4,
        dkv=11,
        name="safethygienemoduleinwall",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=4,
        dkv=15,
        name="safethygienemodule",
        # TODO: Untested model.
    ),
    # ── HVA (dk=20) ─────────────────────────────────────────────────────────────
    SyrConnectModelSignature(
        base_path=None,
        dk=20,
        dkv=19,
        name="hva",
        # TODO: Untested model.
    ),
    # ── Inliner-HWA 3300 (dk=25) ─────────────────────────────────────────────────
    SyrConnectModelSignature(
        base_path=None,
        dk=25,
        dkv=26,
        name="inlinerhwa3300",
        # TODO: Untested model.
    ),
    # ── i-LEX / LEX (dk=40, dkv=16) ─────────────────────────────────────────────
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L10",
        dk=40,
        dkv=16,
        name="l10",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L12",
        dk=40,
        dkv=16,
        name="l12",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L15",
        dk=40,
        dkv=16,
        name="l15",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L20",
        dk=40,
        dkv=16,
        name="l20",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L25",
        dk=40,
        dkv=16,
        name="l25",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L30",
        dk=40,
        dkv=16,
        name="l30",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L40",
        dk=40,
        dkv=16,
        name="l40",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L50",
        dk=40,
        dkv=16,
        name="l50",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L60",
        dk=40,
        dkv=16,
        name="l60",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L70",
        dk=40,
        dkv=16,
        name="l70",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L80",
        dk=40,
        dkv=16,
        name="l80",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L90",
        dk=40,
        dkv=16,
        name="l90",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L100",
        dk=40,
        dkv=16,
        name="l100",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX10",
        dk=40,
        dkv=16,
        name="lex10",
        sbt=1,
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX20",
        dk=40,
        dkv=16,
        name="lex20",
        sbt=2,
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX30",
        dk=40,
        dkv=16,
        name="lex30",
        sbt=3,
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX40",
        dk=40,
        dkv=16,
        name="lex40",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX60",
        dk=40,
        dkv=16,
        name="lex60",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX80",
        dk=40,
        dkv=16,
        name="lex80",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX100",
        dk=40,
        dkv=16,
        name="lex100",
        ver_prefix=None,
    ),
    # ── Hygiene module (dk=60-63) ────────────────────────────────────────────────
    SyrConnectModelSignature(
        base_path=None,
        dk=60,
        dkv=21,
        name="hygienemodulecold",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=61,
        dkv=22,
        name="hygienemodulehot",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=62,
        dkv=23,
        name="hygienemodulehotcold",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=63,
        dkv=24,
        name="hygienemodulecoldhot",
        # TODO: Untested model.
    ),
    # ── LEX Plus 10 (dk=80, dkv=25) ─────────────────────────────────────────────
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEXplus10",
        dk=80,
        dkv=25,
        name="lexplus10",
        sbt=1,
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEXplus10S",
        dk=80,
        dkv=25,
        name="lexplus10s",
        sbt=2,
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        # False (getALA), unlike its lexplus10/lexplus10s siblings: this
        # fixture reports getALA, not getALM, as the current alarm code.
        alarm_style_alm=False,
        base_path=None,
        cna_equals="LEXplus10SL",
        dk=80,
        dkv=25,
        name="lexplus10sl",
        sbt=7,
        ver_prefix=None,
    ),
    # ── CONTROLICmini (dk=100) ───────────────────────────────────────────────────
    SyrConnectModelSignature(
        base_path=None,
        dk=100,
        dkv=27,
        name="controlicmini",
        # TODO: Untested model.
    ),
    # ── SafeFloor (dk=120/122) ───────────────────────────────────────────────────
    SyrConnectModelSignature(
        # dk=120/dkv=34 is shared by multiple vendors; the cloud service tells them
        # apart (`service_branding`).
        base_path=None,
        dk=120,
        dkv=34,
        name="safefloor",
        ver_contains="Floorsensor",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=120,
        dkv=43,
        name="safefloorrwc",
        # TODO: Untested model.
        srn_prefix="43",
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=122,
        dkv=34,
        name="safefloor122",
        # TODO: Untested model.
    ),
    # ── SafeTech / SafeTech+ (dk=140/141/142/145) ────────────────────────────────
    SyrConnectModelSignature(
        base_path="/trio",
        dk=140,
        dkv=35,
        name="safetech",
        # TODO: Untested model. Both values are incorrect in fixture.
        srn_infix="aBC",
        srn_prefix="123",
    ),
    SyrConnectModelSignature(
        base_path="/safe-tec",
        dk=140,
        dkv=35,
        name="safetechv3",
        ver_prefix="Safe-Tech V3",
    ),
    SyrConnectModelSignature(
        base_path="/safe-tec",
        dk=140,
        dkv=35,
        name="safetechv4",
        ver_prefix="Safe-Tech V4",
    ),
    SyrConnectModelSignature(
        # POLYGONVATRO sold these "SYR Safe-Tech Connect" devices together
        # with the AXA building insurance, called "Wasserwächter". Order.-No.: 2422.25.003
        base_path=None,
        # base_path="/safe-tec",
        dk=140,
        dkv=38,
        name="safetechpolygonvatro",
        # TODO: Untested model.
        # srn_prefix="38",
        # Version string: "Safe-Tech V3.53", see https://www.youtube.com/watch?v=apdL8SLZ64Q&t=585s
        # The device reports a version string that looks like "Safe-Tech V4.08" firmware installed.
        # ver_prefix="Safe-Tech V3",
    ),
    SyrConnectModelSignature(
        base_path="/safe-tec",
        dk=140,
        dkv=42,
        name="safetechrwc",
        # TODO: Untested model.
        srn_prefix="42",
    ),
    SyrConnectModelSignature(
        base_path="/pontos-base",
        dk=140,
        dkv=None,
        name="pontosbase",
        # TODO: Untested model.
        ver_prefix="PontosBase",
    ),
    SyrConnectModelSignature(
        base_path=None,
        # base_path="/safe-tec",
        dk=141,
        dkv=35,
        name="safetech141",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        base_path=None,
        dk=142,
        dkv=39,
        name="safetechpluswifi",
        # TODO: Untested model.
        srn_prefix="39",
    ),
    SyrConnectModelSignature(
        base_path=None,
        # base_path="/safe-tec",
        dk=145,
        dkv=35,
        name="safetech145",
        # TODO: Untested model.
    ),
    # ── Specialty devices (dk=160/180/190) ───────────────────────────────────────
    SyrConnectModelSignature(
        # Product number: 3228.15.015
        base_path="/all-in-one",
        dk=160,
        dkv=36,
        name="allinoneplus",
        ver_prefix="All-in-One+",
    ),
    SyrConnectModelSignature(
        base_path="/hygbox",
        dk=180,
        dkv=37,
        name="hygbox",
        # TODO: Untested model.
        srn_prefix="37",
    ),
    SyrConnectModelSignature(
        base_path="/dosing-pump",
        dk=190,
        dkv=44,
        name="dosingpump",
        # TODO: Untested model.
        # Probably the SYR NeoDos Connect; not yet confirmed by the manufacturer.
        # Unverified serial prefix from documentation, missing infix 'AAA' and match condition.
        srn_prefix="2031",
    ),
    # ── Trio LS platform (dk=1100-1113) ──────────────────────────────────────────
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dk=1100,
        dkv=100,
        name="triols",
        # TODO: Untested model.
        srn_prefix="100",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dk=1110,
        dkv=110,
        name="concept200replacementfilter",
        # TODO: Untested model.
        srn_prefix="110",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dk=1111,
        dkv=111,
        name="optimatreplacementfilter",
        # TODO: Untested model.
        srn_prefix="111",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dk=1112,
        dkv=112,
        name="safetechplus",
        srn_prefix="112",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dk=1113,
        dkv=113,
        name="trio",
        srn_prefix="113",
    ),
    # ── NeoSoft platform (dk=1200-1222) ──────────────────────────────────────────
    SyrConnectModelSignature(
        # 5000.00.000 - SYR NeoSoft 5000 Connect
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1200,
        dkv=200,
        name="neosoft5000",
        # TODO: Untested model.
        srn_prefix="200",
    ),
    SyrConnectModelSignature(
        # 2500.00.000 - SYR NeoSoft 2500 Connect
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1206,
        dkv=206,
        name="neosoft2500",
        srn_prefix="206",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1207,
        dkv=207,
        name="sanibelsoftwateruno",
        srn_prefix="207",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1208,
        dkv=208,
        name="conceptsingle",
        # TODO: Untested model.
        srn_prefix="208",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1209,
        dkv=209,
        name="optimasingle",
        # TODO: Untested model.
        srn_prefix="209",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1210,
        dkv=210,
        name="concept200duo",
        # TODO: Untested model.
        srn_prefix="210",
    ),
    SyrConnectModelSignature(
        # 5000.02.700 - Optima T2.3 Doppelenthärtungsanlage, identical to the NeoSoft 5000
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1211,
        dkv=211,
        name="optimat2duo",
        # TODO: Untested model.
        srn_prefix="211",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1212,
        dkv=212,
        name="sanibelsoftwaterduo",
        # TODO: Untested model.
        srn_prefix="212",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1213,
        dkv=213,
        name="optimaduo",
        # TODO: Untested model.
        srn_prefix="213",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1214,
        dkv=214,
        name="conelclearprosofttwin",
        srn_prefix="214",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1215,
        dkv=215,
        name="conelclearprosoft",
        srn_prefix="215",
    ),
    SyrConnectModelSignature(
        # 5000.02.100 - concept 300 Doppelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1216,
        dkv=216,
        name="conceptduo",
        # TODO: Untested model.
        srn_prefix="216",
    ),
    SyrConnectModelSignature(
        # DT3674 - DITECH Doppelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1217,
        dkv=217,
        name="ditechduo",
        # TODO: Untested model.
        srn_prefix="217",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1218,
        dkv=218,
        name="takeduo",
        # TODO: Untested model.
        srn_prefix="218",
    ),
    SyrConnectModelSignature(
        # DT3673 - DITECH Einzelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1219,
        dkv=219,
        name="ditechsingle",
        # TODO: Untested model.
        srn_prefix="219",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1220,
        dkv=220,
        name="takesingle",
        # TODO: Untested model.
        srn_prefix="220",
    ),
    SyrConnectModelSignature(
        # 5000.02.000 - SYR BLACKLANE - NeoSoft Lock Connect II, Doppelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1221,
        dkv=221,
        name="neosoftlock2",
        # TODO: Untested model.
        srn_prefix="221",
    ),
    SyrConnectModelSignature(
        # 2500.02.000 - SYR BLACKLANE - NeoSoft Lock Connect I, Einzelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        dk=1222,
        dkv=222,
        name="neosoftlock1",
        # TODO: Untested model.
        srn_prefix="222",
    ),
    # ── MultiController platform (dk=1500-1506) ──────────────────────────────────
    # The role of a MultiController is getDFM: 1 leak protection, 2 connection centre,
    # 3 All-in-One (dkv 500/506 only), 4 automatic backwash, 5 leak protection with
    # backwash filter (dkv 502-506 only). There is deliberately no generic signature for
    # an unknown role: such a device stays an unknown model, so it gets reported
    # instead of silently showing the global allowlists.
    SyrConnectModelSignature(
        # CLEARPNLS - Retrofit Leakage Protection
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        dk=1500,
        dkv=500,
        name="conelclearproleakprotection",
        srn_prefix="500",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=2,
        dk=1500,
        dkv=500,
        name="conelclearproconnectioncentre",
        # TODO: Untested model.
        srn_prefix="500",
    ),
    SyrConnectModelSignature(
        # CLEARPFSA - Filling Station
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=3,
        dk=1500,
        dkv=500,
        name="conelclearprofill",
        srn_prefix="500",
    ),
    SyrConnectModelSignature(
        # CLEARPMCK - MultiControl-Kit / Backwash System
        # TODO: Untested model.
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        dk=1500,
        dkv=500,
        name="conelclearprobackwash",
        srn_prefix="500",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        dk=1501,
        dkv=501,
        name="sanibelleakprotect",
        srn_prefix="501",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=2,
        dk=1501,
        dkv=501,
        name="sanibelconnectioncentre",
        # TODO: Untested model.
        srn_prefix="501",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        dk=1501,
        dkv=501,
        name="sanibelrsa",
        srn_prefix="501",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        dk=1502,
        dkv=502,
        name="ditechleakprotect",
        # TODO: Untested model.
        srn_prefix="502",
    ),
    SyrConnectModelSignature(
        # DT3645 - DITECH Anschlussmodul Plus, with DT3646 - DITECH MultiControl
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=2,
        dk=1502,
        dkv=502,
        name="ditechconnectioncentre",
        # TODO: Untested model.
        srn_prefix="502",
    ),
    SyrConnectModelSignature(
        # DT3654 - DITECH Rückspülautomatik HWS/RF
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        dk=1502,
        dkv=502,
        name="ditechbackwash",
        # TODO: Untested model.
        srn_prefix="502",
    ),
    SyrConnectModelSignature(
        # DT3676 - DITECH Rückspülfilter Protect
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        dk=1502,
        dkv=502,
        name="ditechbackwashfilter",
        # TODO: Untested model.
        srn_prefix="502",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        dk=1503,
        dkv=503,
        name="takeleakprotect",
        # TODO: Untested model.
        srn_prefix="503",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=2,
        dk=1503,
        dkv=503,
        name="takeconnectioncentre",
        # TODO: Untested model.
        srn_prefix="503",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        dk=1503,
        dkv=503,
        name="takebackwash",
        # TODO: Untested model.
        srn_prefix="503",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        dk=1503,
        dkv=503,
        name="takebackwashfilter",
        # TODO: Untested model.
        srn_prefix="503",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        dk=1504,
        dkv=504,
        name="conceptleakprotect",
        # TODO: Untested model.
        srn_prefix="504",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=2,
        dk=1504,
        dkv=504,
        name="conceptconnectioncentre",
        # TODO: Untested model.
        srn_prefix="504",
    ),
    SyrConnectModelSignature(
        # 2380.01.104 - concept 300 Rückspülautomatik RSA
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        dk=1504,
        dkv=504,
        name="conceptbackwash",
        # TODO: Untested model.
        srn_prefix="504",
    ),
    SyrConnectModelSignature(
        # 2425.01.100 - concept 300 Triofilter mit Leckageschutz
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        dk=1504,
        dkv=504,
        name="concepttriolock",
        # TODO: Untested model.
        srn_prefix="504",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        dk=1505,
        dkv=505,
        name="optimaleakprotect",
        # TODO: Untested model.
        srn_prefix="505",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=2,
        dk=1505,
        dkv=505,
        name="optimaconnectioncentre",
        # TODO: Untested model.
        srn_prefix="505",
    ),
    SyrConnectModelSignature(
        # 2380.01.704 - Optima T2.3 Rückspülautomatik RSA
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        dk=1505,
        dkv=505,
        name="optimabackwash",
        # TODO: Untested model.
        srn_prefix="505",
    ),
    SyrConnectModelSignature(
        # 2425.01.700 - Optima T2.3 Leckageschutz und Rückspülfilter TRIO mit Druckminderer und Lock Flansch
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        dk=1505,
        dkv=505,
        name="optimatriolock",
        # TODO: Untested model.
        srn_prefix="505",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        dk=1506,
        dkv=506,
        name="syrsafetechlockconnect",
        # TODO: Untested model.
        srn_prefix="506",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=2,
        dk=1506,
        dkv=506,
        name="syrac3200connect",
        # TODO: Untested model.
        srn_prefix="506",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=3,
        dk=1506,
        dkv=506,
        name="syrac3228connect",
        # TODO: Untested model.
        srn_prefix="506",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        dk=1506,
        dkv=506,
        name="syrrsaconnect",
        # TODO: Untested model.
        srn_prefix="506",
    ),
    SyrConnectModelSignature(
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        dk=1506,
        dkv=506,
        name="syrtriolockconnect",
        srn_prefix="506",
    ),
)


def detect_model_signature[S: SyrConnectModelSignature](
    status: object,
    signatures: Sequence[S],
    dk: int | None = None,
    dkv: int | None = None,
    sbt: int | None = None,
) -> S | None:
    """Detect the signature of a device from the cloud device kind and its status.

    The cloud API (XML) reports `dk`, `dkv` and `sbt` for every device. They are the
    most reliable match and select the family of signatures with these values; a
    signature without `sbt` matches every subtype. A MultiController reports its role
    in getDFM, the subtype of dk=1500-1506: like `sbt`, a signature with
    `dfm` only matches a device with that role, one without `dfm` every device. A
    family of one signature is the result. In a larger family the status decides, but
    only between its signatures (getCNA for the i-LEX sizes, getVER for SafeTech
    V3/V4). Without a family, e.g. for the local JSON API that has no device kind or
    for a device kind no signature knows, the status decides between all signatures.

    Args:
        status: Flattened device status
        signatures: The signatures to choose from, e.g. `MODEL_SIGNATURES`
        dk: Cloud API deviceKind, None if unknown
        dkv: Cloud API deviceKindVersion, None if unknown
        sbt: Cloud API device subtype, None if unknown

    Returns:
        The matched signature, or None if no signature matches.
    """
    # getDFM is text in the cloud status and a number in the local status
    dfm = str(status.get("getDFM")) if isinstance(status, dict) else None
    candidates = [sig for sig in signatures if sig.dfm is None or str(sig.dfm) == dfm]
    if dk is not None:
        family = [
            sig
            for sig in candidates
            if sig.dk == dk and sig.dkv == dkv and sig.sbt in (None, sbt)
        ]
        if len(family) == 1:
            _LOGGER.debug(
                "Matched signature %s (dk=%s, dkv=%s, sbt=%s, dfm=%s)",
                family[0].name,
                dk,
                dkv,
                sbt,
                dfm,
            )
            return family[0]
        if family:
            return _match_status_values(status, family)
    return _match_status_values(status, candidates)


def _match_status_values[S: SyrConnectModelSignature](
    status: object, signatures: list[S]
) -> S | None:
    """Return the first of the signatures that matches the flattened status.

    Detection priority (highest to lowest):
    1. Serial number prefix (srn_prefix):
        If a signature defines 'srn_prefix', and the serial number (getSRN) starts with srn_prefix + srn_infix, this model is selected immediately.
    2. getCNA exact match (cna_equals):
        If a signature defines 'cna_equals' and getCNA matches, this model is selected.
    3. Version prefix/contains:
        If a signature defines 'ver_prefix' or 'ver_contains', and getVER matches, this model is selected.

    Args:
        status: Flattened device status
        signatures: The signatures to choose from

    Returns:
        The matched signature, or None if none matches.
    """
    if not isinstance(status, dict):
        return None

    # Simple normalizations
    cna = str(status.get("getCNA") or "")
    srn = str(status.get("getSRN") or "")
    ver = str(status.get("getVER") or "")

    def srn_match(sig: SyrConnectModelSignature) -> bool:
        return srn.startswith(f"{sig.srn_prefix}{sig.srn_infix}")

    def ver_match(sig: SyrConnectModelSignature) -> bool:
        ver_prefix = sig.ver_prefix
        ver_contains = sig.ver_contains
        if ver_prefix and not ver.startswith(ver_prefix):
            return False
        if ver_contains and ver_contains not in ver:
            return False
        return True

    # Step 1: Check all serial number prefix matches first (highest priority)
    # If a model signature defines 'srn_prefix' and the serial number matches,
    # return this model immediately. This ensures serial number detection always wins over other methods.
    for sig in signatures:
        if sig.srn_prefix and srn_match(sig):
            _LOGGER.debug("Matched signature %s (srn_prefix)", sig.name)
            return sig

    # Step 2: Check all getCNA (model name) exact matches
    # If a model signature defines 'cna_equals' and getCNA matches, return this model.
    for sig in signatures:
        if sig.cna_equals and cna == sig.cna_equals:
            _LOGGER.debug("Matched signature %s (cna_equals)", sig.name)
            return sig

    # Step 3: Check version matches
    # If version prefix or contains is specified and matches, return this model.
    for sig in signatures:
        if (sig.ver_prefix or sig.ver_contains) and ver_match(sig):
            _LOGGER.debug("Matched signature %s (ver)", sig.name)
            return sig

    _LOGGER.debug("No signature matches; keys found: %s", sorted(status)[:20])
    return None
