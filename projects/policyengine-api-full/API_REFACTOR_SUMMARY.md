# API refactor summary: RESTful user endpoints

## Changes made

### Backend (policyengine-api-full)

#### New user endpoints (`routers/users.py`)

**Enhanced user detail endpoint:**
- `GET /users/{user_id}` - returns user with collated resource counts
  ```json
  {
    "id": "anonymous",
    "username": "anonymous",
    "reports_count": 5,
    "policies_count": 3,
    "datasets_count": 2,
    "simulations_count": 8
  }
  ```

**New RESTful sub-resource endpoints:**
- `GET /users/{user_id}/reports` - list user's reports (with pagination)
- `GET /users/{user_id}/policies` - list user's policies (with pagination)
- `GET /users/{user_id}/datasets` - list user's datasets (with pagination)
- `GET /users/{user_id}/simulations` - list user's simulations (with pagination)

All support `skip` and `limit` query parameters for pagination.

#### Updated reports endpoint (`routers/reports.py`)

- Removed `user_id` query parameter from `GET /reports`
- Now lists all reports globally only
- Added missing `Optional` import

### Frontend (policyengine-app-v2)

#### Updated API client (`app/src/api/v2/userReports.ts`)

Changed `userReportsAPI.list()` to use new endpoint:
```typescript
list: async (userId: string): Promise<any[]> => {
  return await apiClient.get<any[]>(`/users/${userId}/reports`);
}
```

## Testing

✓ Database initialisation working (12,888 baseline parameter values, 676 baseline variables)
✓ API starts successfully
✓ `GET /users/anonymous` returns user with counts
✓ `GET /users/anonymous/reports` returns empty array
✓ All endpoints tested and working

## Migration notes

Since this is alpha, no backwards compatibility maintained. The old `/reports?user_id=X` endpoint no longer filters by user - use `/users/{user_id}/reports` instead.
