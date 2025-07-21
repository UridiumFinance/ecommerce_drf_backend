from rest_framework_api.views import StandardAPIView
from rest_framework import status
from rest_framework.response import Response
from core.permissions import HasValidAPIKey
from django.conf import settings
from django.core.mail import send_mail

from .models import Complaint
from .serializers import ComplaintSerializer


class SubmitComplaintView(StandardAPIView):
    permission_classes = (HasValidAPIKey,)

    def post(self, request):
        data = request.data

        full_name = data.get("fullName")
        last_names = data.get("lastNames")
        identification = data.get("identification")
        telephone = data.get("telephone")
        email = data.get("email")
        address_line1 = data.get("addressLine1")
        address_line2 = data.get("addressLine2")
        city = data.get("city")
        state = data.get("state")
        country = data.get("country")
        postal_code = data.get("postalCode")
        complaint_text = data.get("complaint")
        selected_application = data.get("selectedApplication")
        selected_method = data.get("selectedMethod")

        # Check if there is an existing complaint for this identification that is either pending or processing
        existing_complaint = Complaint.objects.filter(
            identification=identification,
            status__in=['pending', 'processing']
        ).exists()

        if existing_complaint:
            return Response(
                {"success": True, "status": 201, "message": "Complaint created successfully"},
                status=status.HTTP_201_CREATED
            )

        # Create new complaint
        new_complaint = Complaint.objects.create(
            full_name=full_name,
            last_names=last_names,
            identification=identification,
            telephone=telephone,
            email=email,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            state=state,
            country=country,
            postal_code=postal_code,
            complaint=complaint_text,
            selected_application=selected_application,
            selected_method=selected_method,
            status='pending'  # Set the initial status to 'pending'
        )

        # Send email to the user confirming receipt of the complaint
        send_mail(
            subject="Complaint Received",
            message=(
                f"Dear {full_name},\n\n"
                "We have received your complaint and will review it. "
                "You can expect a response from our team within the next 14 days.\n\n"
                "Thank you for reaching out to us."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )

        # Send email to the internal team to notify about the new complaint
        send_mail(
            subject="New Complaint Submitted",
            message=(
                f"A new complaint has been submitted by {full_name} (ID: {identification}).\n\n"
                f"Complaint details:\n{complaint_text}\n\n"
                "Please review this complaint and follow up as necessary."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=["mail@uridium.finance"],
        )

        return Response(
            {"success": True, "status": 201, "message": "Complaint created successfully"},
            status=status.HTTP_201_CREATED
        )
