from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings 
from django.contrib.auth import login, authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import json
import logging
from .forms import CustomUserCreationForm
from .models import CustomUser

# Set up logging
logger = logging.getLogger(__name__)

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = form.cleaned_data['email']
            user.save()
            messages.success(request, 'Account created successfully!')
            return redirect('register')
        else:
            print("Form errors:", form.errors)
            messages.error(request, 'Please fix the errors below.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'usermanage/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Welcome back!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid email or password.')
    
    context = {
        'google_client_id': settings.GOOGLE_CLIENT_ID
    }
    return render(request, 'usermanage/login.html', context)

def dashboard_view(request):
    if request.user.is_authenticated:
        return render(request, 'usermanage/dashboard.html')
    else:
        return redirect('login')

@csrf_exempt
def google_auth(request):
    """
    Handle Google OAuth authentication
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False, 
            'error': 'Only POST method allowed'
        })
    
    try:
        # Parse request data
        data = json.loads(request.body)
        credential = data.get('credential')
        
        if not credential:
            return JsonResponse({
                'success': False,
                'error': 'No credential provided'
            })
        
        # Verify the Google JWT token
        try:
            idinfo = id_token.verify_oauth2_token(
                credential, 
                google_requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )
            
            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid token issuer'
                })
            
            # Extract user information
            google_user_id = idinfo['sub']
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            profile_picture = idinfo.get('picture', '')
            
            logger.info(f"Google user authenticated: {email}")
            
            # Check if user already exists
            try:
                user = CustomUser.objects.get(email=email)
                # User exists, log them in
                login(request, user)
                logger.info(f"Existing user logged in: {email}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Welcome back!',
                    'user_exists': True
                })
                
            except CustomUser.DoesNotExist:
                # Create new user
                try:
                    user = CustomUser.objects.create_user(
                        username=email,  # Use email as username
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        password=None  # No password for Google users
                    )
                    
                    # You could store additional Google info here
                    # user.google_id = google_user_id
                    # user.profile_picture = profile_picture
                    # user.save()
                    
                    login(request, user)
                    logger.info(f"New user created and logged in: {email}")
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Account created successfully! Welcome!',
                        'user_exists': False
                    })
                    
                except Exception as create_error:
                    logger.error(f"Error creating user: {str(create_error)}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Failed to create user account: {str(create_error)}'
                    })
                    
        except ValueError as token_error:
            # Invalid token
            logger.error(f"Invalid Google token: {str(token_error)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid Google token'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in Google auth: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Authentication failed: {str(e)}'
        })

def logout_view(request):
    """
    Handle user logout
    """
    from django.contrib.auth import logout
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')