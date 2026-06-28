"""
Talentick — Organizations Router
فقط super_admin به این endpoint‌ها دسترسی دارد
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import SuperAdmin
from app.schemas.organization import OrganizationCreate, OrganizationResponse, OrganizationUpdate
from app.services import org_service

router = APIRouter()


@router.get("/", response_model=list[OrganizationResponse])
async def list_orgs(
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await org_service.list_organizations(db)


@router.post("/", response_model=OrganizationResponse, status_code=201)
async def create_org(
    body: OrganizationCreate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    existing = await org_service.get_by_slug(db, body.slug)
    if existing:
        raise HTTPException(status_code=400, detail="این slug قبلاً استفاده شده است")
    return await org_service.create_organization(db, body)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_org(
    org_id: uuid.UUID,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    return org


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_org(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    return await org_service.update_organization(db, org, body)


@router.delete("/{org_id}", status_code=204)
async def delete_org(
    org_id: uuid.UUID,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    await org_service.delete_organization(db, org)