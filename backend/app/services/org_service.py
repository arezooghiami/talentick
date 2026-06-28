"""
Talentick — Organization Service
"""
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


async def list_organizations(db: AsyncSession) -> list[Organization]:
    result = await db.execute(select(Organization).order_by(Organization.created_at.desc()))
    return list(result.scalars().all())


async def get_organization(db: AsyncSession, org_id: uuid.UUID) -> Organization | None:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    return result.scalar_one_or_none()


async def get_by_slug(db: AsyncSession, slug: str) -> Organization | None:
    result = await db.execute(select(Organization).where(Organization.slug == slug))
    return result.scalar_one_or_none()


async def create_organization(db: AsyncSession, data: OrganizationCreate) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        slug=data.slug,
        name=data.name,
        name_en=data.name_en,
        description=data.description,
        mission=data.mission,
        vision=data.vision,
        website=data.website,
        phone=data.phone,
        address=data.address,
        settings={},
        plan="pilot",
        is_active=True,
    )
    db.add(org)
    await db.flush()
    return org


async def update_organization(
    db: AsyncSession, org: Organization, data: OrganizationUpdate
) -> Organization:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(org, field, value)
    await db.flush()
    return org


async def delete_organization(db: AsyncSession, org: Organization) -> None:
    await db.delete(org)
    await db.flush()
