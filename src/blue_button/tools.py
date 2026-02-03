import httpx

from src.blue_button.utils import call_api, get_patient_id_from_token


def register_tools(mcp):
    @mcp.tool()
    async def get_patient_info() -> dict:
        """
        Get patient demographic and personal information.
        Returns FHIR Patient resource with name, address, birth date, etc.
        Requires patient/Patient.rs scope.
        """
        result = get_patient_id_from_token()
        if result[0] is None:
            return result[1]
        token, patient_id = result

        try:
            data = await call_api(token.token, f"fhir/Patient/{patient_id}")
            return {"patient_id": patient_id, "data": data}
        except httpx.HTTPStatusError as e:
            return {"error": f"API error: {e.response.status_code}", "detail": str(e)}

    @mcp.tool()
    async def get_coverage_info() -> dict:
        """
        Get Medicare and supplemental coverage information.
        Returns FHIR Coverage resources showing insurance plans and periods.
        Requires patient/Coverage.rs scope.
        """
        result = get_patient_id_from_token()
        if result[0] is None:
            return result[1]
        token, patient_id = result

        try:
            data = await call_api(token.token, f"fhir/Coverage?beneficiary={patient_id}")
            return {"patient_id": patient_id, "coverage": data}
        except httpx.HTTPStatusError as e:
            return {"error": f"API error: {e.response.status_code}", "detail": str(e)}

    @mcp.tool()
    async def get_explanation_of_benefit(eob_id: str | None = None) -> dict:
        """
        Get Medicare claim information (Explanation of Benefit records).
        Returns FHIR ExplanationOfBenefit resources with claim details.
        Requires patient/ExplanationOfBenefit.rs scope.

        Args:
            eob_id: Optional specific EOB ID. If not provided, returns all EOBs.
        """
        result = get_patient_id_from_token()
        if result[0] is None:
            return result[1]
        token, patient_id = result

        try:
            if eob_id:
                endpoint = f"fhir/ExplanationOfBenefit/{eob_id}"
            else:
                endpoint = f"fhir/ExplanationOfBenefit?patient={patient_id}"

            data = await call_api(token.token, endpoint)
            return {"patient_id": patient_id, "claims": data}
        except httpx.HTTPStatusError as e:
            return {"error": f"API error: {e.response.status_code}", "detail": str(e)}

    @mcp.tool()
    async def search_claims(
        service_date_start: str | None = None,
        service_date_end: str | None = None,
        claim_type: str | None = None,
    ) -> dict:
        """
        Search for claims with filters.

        Args:
            service_date_start: Filter claims from this date (YYYY-MM-DD)
            service_date_end: Filter claims to this date (YYYY-MM-DD)
            claim_type: Type of claim (carrier, inpatient, outpatient, snf, hospice, hha, dme, pde)
        """
        result = get_patient_id_from_token()
        if result[0] is None:
            return result[1]
        token, patient_id = result

        params = [f"patient={patient_id}"]
        if service_date_start:
            params.append(f"service-date=ge{service_date_start}")
        if service_date_end:
            params.append(f"service-date=le{service_date_end}")
        if claim_type:
            params.append(f"type={claim_type}")

        try:
            data = await call_api(token.token, f"fhir/ExplanationOfBenefit?{'&'.join(params)}")
            return {
                "patient_id": patient_id,
                "filters": {
                    "service_date_start": service_date_start,
                    "service_date_end": service_date_end,
                    "claim_type": claim_type,
                },
                "results": data,
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"API error: {e.response.status_code}", "detail": str(e)}
