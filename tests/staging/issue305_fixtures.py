from docassemble.EFSPIntegration.py_efsp_client import ApiResponse

class MetadataProxy:
    def __init__(self, mode='null'):
        self.mode = mode
        self.calls = []
    def get_case_type(self, court, code):
        self.calls.append(('type', court, code))
        data = {'name': 'No Cause'} if self.mode == 'valid' else None
        return ApiResponse(200, None, data)
    def get_case_categories(self, court, **kwargs):
        self.calls.append(('category', court))
        data = [{'code': '8730', 'name': 'Summary Process'}] if self.mode == 'valid' else None
        return ApiResponse(200, None, data)
    def get_court(self, court):
        return ApiResponse(200, None, None)
