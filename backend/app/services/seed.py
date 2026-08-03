from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import pseudonymous_id
from app.core.security import hash_password
from app.models.entities import (
    Campaign,
    CampaignScenario,
    CampaignTarget,
    ConsentRecord,
    ContextProfile,
    Department,
    DeliveryAttempt,
    Employee,
    EventLog,
    FailureReason,
    LandingToken,
    Organization,
    RiskScore,
    Role,
    Scenario,
    ScenarioVersion,
    TrainingAssignment,
    TrainingCompletion,
    TrainingModule,
    User,
    UserRoleLink,
)
from app.models.enums import (
    CampaignStatus,
    CampaignType,
    Channel,
    ConsentStatus,
    DeliveryStatus,
    DifficultyLevel,
    EmployeeStatus,
    EventType,
    ScenarioStatus,
    UserRole,
)
from app.services.policy_engine import get_or_create_policy
from app.services.profiling import build_context_profile
from app.services.scoring import recalculate_employee_risk

DEPARTMENTS = [
    ("Finance", "FIN"),
    ("HR", "HR"),
    ("IT", "IT"),
    ("Sales", "SLS"),
    ("Operations", "OPS"),
]

ROLE_MIX = {
    "Finance": ["Finance Analyst", "Accounts Manager", "Procurement Specialist"],
    "HR": ["HR Business Partner", "Recruitment Coordinator", "People Ops Manager"],
    "IT": ["IT Support Engineer", "Security Analyst", "Systems Administrator"],
    "Sales": ["Account Executive", "Sales Operations Specialist", "Regional Sales Manager"],
    "Operations": ["Operations Analyst", "Project Coordinator", "Facilities Lead"],
}

FIRST_NAMES = [
    "Amina", "Hamza", "Sana", "Bilal", "Noor", "Farah", "Usman", "Zara", "Rayan", "Hina",
    "Mariam", "Tariq", "Dania", "Ali", "Eman", "Saad", "Maha", "Omar", "Nimra", "Yasir",
]
LAST_NAMES = [
    "Khan", "Ahmed", "Shah", "Malik", "Iqbal", "Raza", "Siddiqui", "Qureshi", "Farooq", "Hussain",
]

FAILURE_REASONS = [
    ("urgency", "Urgency", "The scenario pushed a rushed decision."),
    ("authority", "Authority", "The scenario leaned on implied authority."),
    ("curiosity", "Curiosity", "The content triggered curiosity."),
    ("reward", "Reward", "The scenario hinted at benefit or reward."),
    ("fear", "Fear", "The scenario used negative outcome pressure."),
    ("qr_lure", "QR lure", "The scenario used QR convenience."),
    ("sms_trust", "SMS trust", "The message relied on familiar SMS patterns."),
    ("voice_pressure", "Voice pressure", "A live caller applied real-time social pressure."),
    ("synthetic_likeness", "Synthetic likeness", "A familiar voice or face was trusted as proof of identity."),
    ("habit_autopilot", "Habit/autopilot", "Routine processing reduced caution."),
    ("role_relevance", "Role relevance", "The lure fit the employee workflow."),
]

TRAINING_MODULES = [
    (
        "Email triage in 45 seconds",
        "email",
        "urgency",
        ["Slow down", "Check sender context", "Use report button"],
        "Recognize urgency tactics in email simulations.",
    ),
    (
        "QR pause-check-report",
        "qr",
        "qr_lure",
        ["Look for owned domain", "Expect a training banner", "Verify destination"],
        "Safe guidance for QR scanning.",
    ),
    (
        "SMS verification habits",
        "sms",
        "sms_trust",
        ["Avoid rushing", "Use internal directory", "Open only approved links"],
        "SMS awareness micro-training.",
    ),
    (
        "Hang up, look up, call back",
        "vishing",
        "voice_pressure",
        [
            "Never act on a request while still on the inbound call",
            "Find the number yourself in the internal directory",
            "A caller who resists a call-back is the tell",
        ],
        "A caller cannot prove who they are over the phone. Verification means ending the call and "
        "dialling a number you looked up yourself. Real colleagues expect this and will not object.",
    ),
    (
        "Recognition is not verification",
        "deepfake",
        "synthetic_likeness",
        [
            "A familiar voice or face is a claim, not proof",
            "Confirm high-value requests on a channel you chose",
            "Treat requests for secrecy as the red flag they are",
        ],
        "Synthetic voice and video are now cheap enough to target ordinary approval workflows. "
        "The only control that survives a convincing fake is out-of-band verification through a "
        "channel the sender did not choose for you.",
    ),
    (
        "General social engineering signs",
        "general",
        "habit_autopilot",
        ["Pause", "Verify", "Report"],
        "General awareness refresher.",
    ),
]

DEMO_EMPLOYEE_EMAIL_SUFFIX = "@northwind.example.com"
VALIDATION_EMPLOYEE_NAMES = {"UI Flow Demo"}
DEMO_CAMPAIGN_NAMES = {"Quarterly Finance Awareness Drill", "UI Flow Validation"}
DEMO_CAMPAIGN_DESCRIPTIONS = {"Seeded sandbox campaign for the FYP demo.", "End to end validation campaign"}
DEMO_DEPARTMENT_NAMES = {name for name, _ in DEPARTMENTS} | {"Demo DDA591"}
DEMO_DEPARTMENT_CODES = {code for _, code in DEPARTMENTS} | {"DDA591"}


def seed_database(db: Session) -> None:
    roles = ensure_roles(db)
    organization = ensure_organization(db)
    users = ensure_default_users(db, organization, roles)
    ensure_failure_reasons(db)
    ensure_training_modules(db, organization)
    get_or_create_policy(db, organization.id)
    db.flush()

    if settings.seed_demo_content:
        ensure_demo_directory_data(db, organization, users)
    else:
        remove_legacy_demo_content(db, organization)

    db.commit()


def ensure_roles(db: Session) -> dict[UserRole, Role]:
    roles: dict[UserRole, Role] = {}
    for role_name in UserRole:
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(name=role_name)
            db.add(role)
            db.flush()
        roles[role_name] = role
    return roles


def ensure_organization(db: Session) -> Organization:
    organization = db.query(Organization).filter(Organization.slug == settings.demo_org_slug).first()
    if organization:
        return organization

    organization = Organization(
        name=settings.demo_org_name,
        slug=settings.demo_org_slug,
        timezone="Asia/Karachi",
    )
    db.add(organization)
    db.flush()
    return organization


def ensure_default_users(db: Session, organization: Organization, roles: dict[UserRole, Role]) -> dict[str, User]:
    defaults = {
        "admin@breachsim-lab.com": ("Aisha Rahman", "Admin123!", UserRole.ADMIN),
        "manager@breachsim-lab.com": ("Bilal Siddiqui", "Manager123!", UserRole.CAMPAIGN_MANAGER),
        "auditor@breachsim-lab.com": ("Noor Fatima", "Auditor123!", UserRole.AUDITOR),
        "reviewer@breachsim-lab.com": ("Rayan Khan", "Reviewer123!", UserRole.ADMIN),
    }

    users: dict[str, User] = {}
    for email, (full_name, password, role_name) in defaults.items():
        user = (
            db.query(User)
            .filter(User.organization_id == organization.id, User.email == email)
            .first()
        )
        if not user:
            user = User(
                organization_id=organization.id,
                email=email,
                full_name=full_name,
                password_hash=hash_password(password),
            )
            db.add(user)
            db.flush()
        if not db.query(UserRoleLink).filter(UserRoleLink.user_id == user.id, UserRoleLink.role_id == roles[role_name].id).first():
            db.add(UserRoleLink(user_id=user.id, role_id=roles[role_name].id))
        users[email] = user
    db.flush()
    return users


def ensure_failure_reasons(db: Session) -> None:
    existing_codes = {row.code for row in db.query(FailureReason).all()}
    for code, label, description in FAILURE_REASONS:
        if code in existing_codes:
            continue
        db.add(FailureReason(code=code, label=label, description=description))
    db.flush()


def ensure_training_modules(db: Session, organization: Organization) -> None:
    existing_titles = {
        row.title
        for row in db.query(TrainingModule).filter(TrainingModule.organization_id == organization.id).all()
    }
    for title, vector, reason_code, guidance_points, body in TRAINING_MODULES:
        if title in existing_titles:
            continue
        db.add(
            TrainingModule(
                organization_id=organization.id,
                title=title,
                vector=vector,
                primary_reason_code=reason_code,
                duration_seconds=45,
                guidance_points=guidance_points,
                body=body,
            )
        )
    db.flush()


def ensure_demo_directory_data(db: Session, organization: Organization, users: dict[str, User]) -> None:
    if db.query(Employee).filter(Employee.organization_id == organization.id).count():
        return

    departments: dict[str, Department] = {}
    for name, code in DEPARTMENTS:
        department = Department(organization_id=organization.id, name=name, code=code)
        db.add(department)
        db.flush()
        departments[name] = department

    employees: list[Employee] = []
    for index in range(50):
        department_name = DEPARTMENTS[index % len(DEPARTMENTS)][0]
        role_title = ROLE_MIX[department_name][index % len(ROLE_MIX[department_name])]
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index * 3) % len(LAST_NAMES)]
        employee = Employee(
            organization_id=organization.id,
            department_id=departments[department_name].id,
            employee_id=f"EMP-{1000 + index}",
            full_name=f"{first} {last}",
            email=f"{first.lower()}.{last.lower()}{index}{DEMO_EMPLOYEE_EMAIL_SUFFIX}",
            phone=f"+92300123{index:04d}",
            role_title=role_title,
            approved_context_summary=f"Approved workflow notes for {department_name.lower()} approvals and internal communications.",
            approved_public_profile_summary=f"Employee profile supplied by organization for {department_name.lower()} role context.",
            training_preferences=["email", "micro-card"],
            consent_status=ConsentStatus.CONSENTED if index % 5 else ConsentStatus.PENDING,
            status=EmployeeStatus.ACTIVE,
            risk_score=(index * 3) % 55,
        )
        db.add(employee)
        db.flush()
        db.add(ConsentRecord(employee_id=employee.id, status=employee.consent_status, source="seed"))
        build_context_profile(db, employee)
        employees.append(employee)

    sample_targets = employees[:5]
    finance_profile = sample_targets[0].context_profiles[0]
    manager = users["manager@breachsim-lab.com"]
    admin = users["admin@breachsim-lab.com"]
    reviewer = users["reviewer@breachsim-lab.com"]

    scenario = Scenario(
        organization_id=organization.id,
        created_by_user_id=manager.id,
        profile_id=finance_profile.id,
        title="Invoice/Payment Approval: review requested",
        channel=Channel.EMAIL,
        theme="invoice/payment approval",
        difficulty_level=DifficultyLevel.MEDIUM,
        status=ScenarioStatus.APPROVED,
        approved_by_user_id=admin.id,
        detected_persuasion_triggers=["authority", "role-relevance"],
        policy_validation={"passed": True, "warnings": ["Training label included"]},
    )
    db.add(scenario)
    db.flush()

    version = ScenarioVersion(
        scenario_id=scenario.id,
        version_number=1,
        created_by_user_id=manager.id,
        subject="Invoice/Payment Approval: review requested",
        body_copy="Hello, this internal training simulation references an invoice approval workflow. Pause and verify sender context before acting.",
        cta_text="Review Securely",
        landing_page_copy="Training simulation only. No real credentials are stored.",
        rationale_metadata={"theme": "invoice/payment approval", "channel": "email"},
        detected_persuasion_triggers=["authority", "role-relevance"],
        difficulty_score=52,
        validation_result={"passed": True, "warnings": []},
    )
    db.add(version)
    db.flush()
    scenario.current_version_id = version.id

    campaign = Campaign(
        organization_id=organization.id,
        created_by_user_id=manager.id,
        approved_by_user_id=admin.id,
        second_approved_by_user_id=reviewer.id,
        name="Quarterly Finance Awareness Drill",
        description="Seeded sandbox campaign for the FYP demo.",
        channel=Channel.EMAIL,
        campaign_type=CampaignType.ONE_TIME,
        status=CampaignStatus.APPROVED,
        throttling_per_hour=25,
        requires_second_approval=True,
        sandbox_mode=True,
        learning_objective="Recognize finance-targeted approval lures.",
        target_filters={"department": "Finance"},
    )
    db.add(campaign)
    db.flush()
    db.add(CampaignScenario(campaign_id=campaign.id, scenario_id=scenario.id))

    for index, employee in enumerate(sample_targets):
        db.add(CampaignTarget(campaign_id=campaign.id, employee_id=employee.id, target_group_label="seeded-demo"))
        attempt = DeliveryAttempt(
            campaign_id=campaign.id,
            employee_id=employee.id,
            scenario_id=scenario.id,
            channel=Channel.EMAIL,
            status=DeliveryStatus.SANDBOXED,
            sandbox_mode=True,
            preview_payload={
                "subject": version.subject,
                "body_copy": version.body_copy,
                "cta_text": version.cta_text,
                "preview_url": f"http://localhost:3000/training/{pseudonymous_id(str(campaign.id), str(employee.id), str(index))[:24]}",
            },
        )
        db.add(attempt)
        db.flush()
        token_value = pseudonymous_id(str(campaign.id), str(employee.id), str(index))[:24]
        token = LandingToken(
            delivery_attempt_id=attempt.id,
            employee_id=employee.id,
            campaign_id=campaign.id,
            token=token_value,
            landing_type="email",
        )
        db.add(token)
        db.flush()
        db.add(
            EventLog(
                organization_id=organization.id,
                employee_id=employee.id,
                campaign_id=campaign.id,
                delivery_attempt_id=attempt.id,
                landing_token_id=token.id,
                event_type=EventType.DELIVERED,
                channel=Channel.EMAIL,
                event_metadata={"sandbox_mode": True},
                pseudo_event_id=pseudonymous_id(str(organization.id), str(employee.id), "delivered", str(index)),
            )
        )
        db.add(
            EventLog(
                organization_id=organization.id,
                employee_id=employee.id,
                campaign_id=campaign.id,
                delivery_attempt_id=attempt.id,
                landing_token_id=token.id,
                event_type=EventType.CLICKED_LINK if index % 2 == 0 else EventType.CLICKED_REPORT,
                channel=Channel.EMAIL,
                event_metadata={"reason": "seeded-click" if index % 2 == 0 else "seeded-report"},
                pseudo_event_id=pseudonymous_id(
                    str(organization.id),
                    str(employee.id),
                    "clicked_link" if index % 2 == 0 else "clicked_report",
                    str(index),
                ),
            )
        )

    db.flush()
    for employee in sample_targets:
        recalculate_employee_risk(db, employee)
    db.flush()


def remove_legacy_demo_content(db: Session, organization: Organization) -> None:
    employees = db.query(Employee).filter(Employee.organization_id == organization.id).all()
    removable_employees = [
        employee
        for employee in employees
        if employee.email.endswith(DEMO_EMPLOYEE_EMAIL_SUFFIX) or employee.full_name in VALIDATION_EMPLOYEE_NAMES
    ]
    if not removable_employees:
        remove_empty_demo_departments(db, organization)
        return

    removable_employee_ids = {employee.id for employee in removable_employees}
    removable_profiles = (
        db.query(ContextProfile)
        .filter(ContextProfile.employee_id.in_(removable_employee_ids))
        .all()
    )
    removable_profile_ids = {profile.id for profile in removable_profiles}

    removable_scenarios = [
        scenario
        for scenario in db.query(Scenario).filter(Scenario.organization_id == organization.id).all()
        if scenario.profile_id in removable_profile_ids
    ]
    removable_scenario_ids = {scenario.id for scenario in removable_scenarios}

    removable_campaign_ids = set()
    for campaign in db.query(Campaign).filter(Campaign.organization_id == organization.id).all():
        target_ids = {target.employee_id for target in campaign.targets}
        if (
            campaign.name in DEMO_CAMPAIGN_NAMES
            or campaign.description in DEMO_CAMPAIGN_DESCRIPTIONS
            or (target_ids and target_ids.issubset(removable_employee_ids))
        ):
            removable_campaign_ids.add(campaign.id)

    removable_attempt_ids = {
        attempt.id
        for attempt in db.query(DeliveryAttempt).all()
        if attempt.employee_id in removable_employee_ids
        or attempt.campaign_id in removable_campaign_ids
        or attempt.scenario_id in removable_scenario_ids
    }
    removable_assignment_ids = {
        assignment.id
        for assignment in db.query(TrainingAssignment).all()
        if assignment.employee_id in removable_employee_ids or assignment.campaign_id in removable_campaign_ids
    }

    if removable_assignment_ids:
        db.query(TrainingCompletion).filter(
            TrainingCompletion.assignment_id.in_(removable_assignment_ids)
        ).delete(synchronize_session=False)
        db.query(TrainingAssignment).filter(
            TrainingAssignment.id.in_(removable_assignment_ids)
        ).delete(synchronize_session=False)

    if removable_attempt_ids:
        db.query(EventLog).filter(
            (EventLog.delivery_attempt_id.in_(removable_attempt_ids))
            | (EventLog.employee_id.in_(removable_employee_ids))
            | (EventLog.campaign_id.in_(removable_campaign_ids))
        ).delete(synchronize_session=False)
        db.query(LandingToken).filter(
            (LandingToken.delivery_attempt_id.in_(removable_attempt_ids))
            | (LandingToken.employee_id.in_(removable_employee_ids))
            | (LandingToken.campaign_id.in_(removable_campaign_ids))
        ).delete(synchronize_session=False)
        db.query(DeliveryAttempt).filter(
            DeliveryAttempt.id.in_(removable_attempt_ids)
        ).delete(synchronize_session=False)
    else:
        db.query(EventLog).filter(
            (EventLog.employee_id.in_(removable_employee_ids))
            | (EventLog.campaign_id.in_(removable_campaign_ids))
        ).delete(synchronize_session=False)

    if removable_campaign_ids:
        db.query(CampaignTarget).filter(
            (CampaignTarget.campaign_id.in_(removable_campaign_ids))
            | (CampaignTarget.employee_id.in_(removable_employee_ids))
        ).delete(synchronize_session=False)
        db.query(CampaignScenario).filter(
            (CampaignScenario.campaign_id.in_(removable_campaign_ids))
            | (CampaignScenario.scenario_id.in_(removable_scenario_ids))
        ).delete(synchronize_session=False)
        db.query(Campaign).filter(Campaign.id.in_(removable_campaign_ids)).delete(synchronize_session=False)

    if removable_scenario_ids:
        for scenario in removable_scenarios:
            scenario.current_version_id = None
        db.flush()
        db.query(ScenarioVersion).filter(
            ScenarioVersion.scenario_id.in_(removable_scenario_ids)
        ).delete(synchronize_session=False)
        db.query(Scenario).filter(
            Scenario.id.in_(removable_scenario_ids)
        ).delete(synchronize_session=False)

    db.query(RiskScore).filter(
        RiskScore.employee_id.in_(removable_employee_ids)
    ).delete(synchronize_session=False)
    db.query(ContextProfile).filter(
        ContextProfile.id.in_(removable_profile_ids)
    ).delete(synchronize_session=False)
    db.query(ConsentRecord).filter(
        ConsentRecord.employee_id.in_(removable_employee_ids)
    ).delete(synchronize_session=False)
    db.query(Employee).filter(
        Employee.id.in_(removable_employee_ids)
    ).delete(synchronize_session=False)

    remove_empty_demo_departments(db, organization)
    db.flush()


def remove_empty_demo_departments(db: Session, organization: Organization) -> None:
    for department in db.query(Department).filter(Department.organization_id == organization.id).all():
        has_employees = db.query(Employee).filter(Employee.department_id == department.id).count() > 0
        is_demo_department = department.name in DEMO_DEPARTMENT_NAMES or department.code in DEMO_DEPARTMENT_CODES
        if has_employees or not is_demo_department:
            continue
        db.query(RiskScore).filter(RiskScore.department_id == department.id).delete(synchronize_session=False)
        db.query(Department).filter(Department.id == department.id).delete(synchronize_session=False)
