from GoogleDriveToS3 import upload_drive_folder_to_s3
from OrganizeS3Data import organize_s3_folder

# # Upload and organize House Committee documents
# upload_drive_folder_to_s3(
#     folder_id="1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz",
#     s3_prefix="HC/",
#     folder_name="House Committee"
# )

# organize_s3_folder(
#     source_prefix="HC/",
#     organized_prefix="HC_organized/",
#     delete_originals=False,
#     folder_name="House Committee"
# )

# Upload and organize Epstein Estate documents
upload_drive_folder_to_s3(
    folder_id="1hTNH5woIRio578onLGElkTWofUSWRoH_",
    s3_prefix="EpsteinEstate/",
    folder_name="Epstein Estate"
)

organize_s3_folder(
    source_prefix="EpsteinEstate/",
    organized_prefix="EpsteinEstate_organized/",
    delete_originals=False,
    folder_name="Epstein Estate"
)

print("\n" + "="*60)
print("ALL UPLOADS AND ORGANIZATION COMPLETE!")
print("="*60)
