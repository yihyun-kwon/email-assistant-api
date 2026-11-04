


from app.repositories.email_repository import EmailRepository
class EmailService:

    def __init__(self, repository: EmailRepository):
        self.repository = repository
