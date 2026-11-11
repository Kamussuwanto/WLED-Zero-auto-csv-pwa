


import requests
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import ElectronicPart, ElectronicTool


import csv
import io

#from django.shortcuts import render, redirect
from django.db.models import Q
#from .models import ElectronicPart, ElectronicTool


# inventory/views.py

# Option A: Use the static IP directly (Recommended if mDNS has latency over your phone hotspot)
MCU_ADDRESS = "http://192.168.43.40"

# Option B: Use the mDNS alias domain name 
# MCU_ADDRESS = "http://electronics-leds.local"

# Using mDNS local hostname instead of a hardcoded IP address
#MCU_ADDRESS = "http://electronics-leds.local"

def locate_part(request, pk):
    """Sends an HTTP request to the ESP32-S3 to light up a part's drawer."""
    part = get_object_or_404(ElectronicPart, pk=pk)
    return _send_led_signal(request, part.name, part.led_index)

def locate_tool(request, pk):
    """Sends an HTTP request to the ESP32-S3 to light up a tool's drawer."""
    tool = get_object_or_404(ElectronicTool, pk=pk)
    return _send_led_signal(request, tool.name, tool.led_index)

def _send_led_signal(request, item_name, led_index):
    """Helper function to execute the outbound API request to the hardware."""
    try:
        # Calls the ESP32-S3 route: http://electronics-leds.local
        response = requests.get(f"{MCU_ADDRESS}/light", params={'led': led_index}, timeout=2.5)
        
        if response.status_code == 200:
            messages.success(request, f"⚡ Flashing drawer LED {led_index} for: {item_name}!")
        else:
            messages.warning(request, f"MCU responded with status code {response.status_code}.")
            
    except requests.exceptions.RequestException:
        messages.error(
            request, 
            f"❌ Hardware offline. Ensure your ESP32-S3 is powered and on your phone's hotspot."
        )
        
    # Redirect back to the page the user came from
    return redirect(request.META.get('HTTP_REFERER', '/'))






def inventory_search_view(request):
    # --- Handle POST requests (Adding, Updating stock, or Deleting items) ---
    if request.method == 'POST':
        form_action = request.POST.get('form_action')

        # Scenario A: Adding a Brand New Item
        if form_action == 'add_item':
            item_type = request.POST.get('add_item_type')
            name = request.POST.get('name')
            qty = int(request.POST.get('quantity', 0))

            if name:
                if item_type == 'tool':
                    ElectronicTool.objects.create(
                        name=name,
                        brand=request.POST.get('brand', ''),
                        serial_number=request.POST.get('serial_number', ''),
                        quantity=qty
                    )
                elif item_type == 'part':
                    ElectronicPart.objects.create(
                        name=name,
                        part_number=request.POST.get('part_number', ''),
                        value=request.POST.get('value', ''),
                        package_type=request.POST.get('package_type', ''),
                        storage_location=request.POST.get('storage_location', ''),
                        quantity=qty
                    )

        # Scenario B: Inline Stock Modification
        elif form_action == 'update_stock':
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            new_quantity = request.POST.get('quantity')

            try:
                qty = int(new_quantity)
                if qty >= 0:
                    if item_type == 'tool':
                        tool = ElectronicTool.objects.get(id=item_id)
                        tool.quantity = qty
                        tool.save()
                    elif item_type == 'part':
                        part = ElectronicPart.objects.get(id=item_id)
                        part.quantity = qty
                        part.save()
            except (ValueError, ElectronicTool.DoesNotExist, ElectronicPart.DoesNotExist):
                pass

        # Scenario C: Deleting an Item Completely
        elif form_action == 'delete_item':
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')

            try:
                if item_type == 'tool':
                    ElectronicTool.objects.get(id=item_id).delete()
                elif item_type == 'part':
                    ElectronicPart.objects.get(id=item_id).delete()
            except (ElectronicTool.DoesNotExist, ElectronicPart.DoesNotExist):
                pass

        # Retain search query params across submissions
        query_string = request.GET.urlencode()
        url = request.path
        if query_string:
            url += f'?{query_string}'
        return redirect(url)

    # --- Handle GET requests (Displaying the tables and searching) ---
    query = request.GET.get('q')
    parts = ElectronicPart.objects.all()
    tools = ElectronicTool.objects.all()

    if query:
        parts = parts.filter(
            Q(name__icontains=query) |
            Q(part_number__icontains=query) |
            Q(value__icontains=query)
        )
        tools = tools.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(serial_number__icontains=query)
        )

    context = {
        'parts': parts,
        'tools': tools,
        'query': query
    }
    return render(request, 'inventory/part_list.html', context)




def bulk_import_parts(request):
    """Parses an uploaded CSV file and imports components directly into the database database."""
    if request.method == "POST":
        csv_file = request.FILES.get('csv_file')
        
        # Validation checks
        if not csv_file:
            messages.error(request, "Please upload a CSV file.")
            return redirect('part_list') # Redirect back to your inventory dashboard view
            
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Invalid file format. Please upload a standard .csv extension file.")
            return redirect('part_list')

        try:
            # Read file stream safely as text string layer
            data_set = csv_file.read().decode('UTF-8')
            io_string = io.StringIO(data_set)
            
            # Skip the column names header row
            next(io_string)
            

            created_count = 0
            for row in csv.reader(io_string, delimiter=','):
                # Skip blank or incomplete rows
                if not row or len(row) < 3:
                    continue
                    
                # Extract columns cleanly (Name, LED Index, Quantity are standard core inputs)
                name_val = row[0].strip()
                led_index_val = int(row[1].strip()) if row[1].strip().isdigit() else 0
                quantity_val = int(row[2].strip()) if row[2].strip().isdigit() else 0
                
                # Check for optional metadata fields in rows, fall back to empty string if not provided
                part_num_val = row[3].strip() if len(row) > 3 else ""
                value_val = row[4].strip() if len(row) > 4 else ""
                package_val = row[5].strip() if len(row) > 5 else ""
                location_val = row[6].strip() if len(row) > 6 else ""

                # Commit directly to the verified database model schema
                ElectronicPart.objects.create(
                    name=name_val,
                    led_index=led_index_val,
                    quantity=quantity_val,
                    part_number=part_num_val,
                    value=value_val,
                    package_type=package_val,
                    storage_location=location_val
                )
                created_count += 1

            
                
            messages.success(request, f"🎉 Successfully bulk-imported {created_count} new parts into the database database!")
            
        except Exception as e:
            messages.error(request, f"❌ Error processing file: {str(e)}")
            
        return redirect('part_list')
        
    return redirect('part_list')
